"""Full graph publication → private reassessment. Every policy and profile is synthetic."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.agents.graph import WorkflowRunner
from app.auth.encryption import unseal
from app.ingestion.fetcher import FetchResponse
from app.models import Assessment, BackgroundJob, Notification, PolicyChange, ReassessmentEvent, SourceMonitor
from app.services.monitoring import compare_change, monitor_document, process_change_document
from app.services.reassessment import reassess_change
from tests.ingestion_support import TEXT, FixtureProvider, candidate_batch, pdf_content
from tests.test_citizen import signup
from tests.test_monitoring import setup_monitor
from tests.test_phase4_workflow import approval_body, corrected_review
from tests.test_phase4_workflow import workflow_context as workflow_context


async def publish_update(client, session, context, config, monkeypatch):
    app, headers, scheme, document, workflow, _ = context
    identifier = (await client.post(f"/api/v1/admin/monitors/{config['id']}/check", headers=headers)).json()[
        "job_id"
    ]
    job = await session.get(BackgroundJob, UUID(identifier))
    new_text = TEXT.replace("18", "19")
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(return_value=FetchResponse(200, pdf_content(new_text), "new-synthetic.pdf")),
    )
    await monitor_document(session, app.state.settings, job)

    class Changed(FixtureProvider):
        async def extract(self, context):
            batch = candidate_batch(context["scheme_id"], context["source_document_version"])
            batch.candidates[0].nodes[0].expected_value = 19
            batch.candidates[0].evidence[0].supporting_excerpt = new_text
            return batch

    runner = WorkflowRunner(app.state.settings, app.state.workflow_runner.sessions, Changed())
    app.state.workflow_runner = runner
    docjob = await session.scalar(select(BackgroundJob).where(BackgroundJob.kind == "DOCUMENT"))
    await process_change_document(session, app.state.settings, docjob, runner)
    change = await session.scalar(select(PolicyChange))
    await compare_change(session, change.id)
    await session.commit()
    assert (await reassess_change(session, app.state.settings, change.id))["skipped"] == "unapproved_change"
    pending = (await client.get(f"/api/v1/admin/workflows/{change.workflow_id}")).json()
    review = await corrected_review(client, headers, pending)
    review["draft"].update(
        replaces_rule_set_ids=[str(change.old_rule_set_id)],
        replacement_notes="Synthetic same-scope replacement retaining immutable historical policy.",
    )
    review = (
        await client.post(
            f"/api/v1/admin/reviews/{review['id']}/revisions",
            headers=headers,
            json={
                "expected_revision": 2,
                "draft": review["draft"],
                "notes": "Synthetic complete policy review of the new threshold and source.",
            },
        )
    ).json()
    approved = await client.post(
        f"/api/v1/admin/policy-changes/{change.id}/approve", headers=headers, json=approval_body(review)
    )
    assert approved.status_code == 200, approved.text
    await session.refresh(change)
    return change


@pytest.mark.parametrize("mode", ["consented", "missing_profile", "notifications_off", "reassessment_off"])
async def test_verified_publication_reassessment_and_preferences(
    client, session, workflow_context, monkeypatch, mode
):
    app, headers, scheme, document, workflow, _ = workflow_context
    app.state.settings = app.state.settings.model_copy(
        update={"profile_encryption_key": SecretStr(Fernet.generate_key().decode())}
    )
    config = await setup_monitor(client, session, workflow_context)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as citizen:
        account, ch = await signup(citizen)
        assert (
            await citizen.put("/api/v1/profiles/me", headers=ch, json={"age_years": 18})
        ).status_code == 200
        response = await citizen.post(
            "/api/v1/assessments",
            headers=ch,
            json={"scheme_id": str(scheme.id), "request_key": str(uuid4()), "allow_reassessment": True},
        )
        assert response.status_code == 201, response.text
        original = response.json()
        assert original["result"] == "PASS"
        if mode == "missing_profile":
            assert (await citizen.delete("/api/v1/profiles/me", headers=ch)).status_code == 204
        if mode in {"notifications_off", "reassessment_off"}:
            assert (
                await citizen.put(
                    "/api/v1/notification-preferences",
                    headers=ch,
                    json={
                        "in_app": mode != "notifications_off",
                        "automatic_reassessment": mode != "reassessment_off",
                        "policy_updates": True,
                    },
                )
            ).status_code == 200
        change = await publish_update(client, session, workflow_context, config, monkeypatch)
        job = await session.scalar(select(BackgroundJob).where(BackgroundJob.kind == "REASSESS"))
        assert job and job.payload == {"change_id": str(change.id)}
        result = await reassess_change(session, app.state.settings, change.id)
        assert result["reassessed"] == (0 if mode == "reassessment_off" else 1)
        assert result["notified"] == (0 if mode == "notifications_off" else 1)
        assert (await citizen.get(f"/api/v1/assessments/{original['id']}")).json()["result"] == "PASS"
        assert (await citizen.post(f"/api/v1/assessments/{original['id']}/reproduce", headers=ch)).json()[
            "matches_original"
        ]
        event = await session.scalar(select(ReassessmentEvent))
        assert event.user_id == UUID(account["user_id"])
        if mode != "reassessment_off":
            new = (await citizen.get(f"/api/v1/assessments/{event.new_assessment_id}")).json()
            assert new["result"] == ("UNKNOWN" if mode == "missing_profile" else "FAIL")
            assert new["parent_id"] == original["id"] and new["rule_set_id"] != original["rule_set_id"]
            impact = unseal(app.state.settings, event.user_id, f"impact:{event.id}", event.encrypted_impact)
            assert impact["condition_changes"] and impact["result_changed"]
        assert (await reassess_change(session, app.state.settings, change.id))["reassessed"] == 0
        assert await session.scalar(select(func.count()).select_from(ReassessmentEvent)) == 1
        assert await session.scalar(select(func.count()).select_from(Notification)) == (
            0 if mode == "notifications_off" else 1
        )
        if mode != "notifications_off":
            notices = (await citizen.get("/api/v1/notifications")).json()
            assert notices["unread_count"] == 1
            notification = notices["items"][0]
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as unrelated:
                _, uh = await signup(unrelated)
                assert (await unrelated.get("/api/v1/notifications")).json()["total"] == 0
                assert (
                    await unrelated.post(f"/api/v1/notifications/{notification['id']}/read", headers=uh)
                ).status_code == 404
            assert (
                await citizen.post(f"/api/v1/notifications/{notification['id']}/read", headers=ch)
            ).status_code == 204
            assert (await citizen.post("/api/v1/notifications/read-all", headers=ch)).status_code == 204
            assert (await citizen.get("/api/v1/notifications")).json()["unread_count"] == 0
        # Deletion must remove the self-referencing assessment chain, not policy history.
        from tests.ingestion_support import PASSWORD

        deleted = await citizen.request(
            "DELETE",
            "/api/v1/me",
            headers=ch,
            json={"current_password": PASSWORD, "acknowledge_deletion": True},
        )
        assert deleted.status_code == 204, deleted.text
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.user_id == UUID(account["user_id"]))
            )
            == 0
        )
        assert await session.scalar(select(func.count()).select_from(PolicyChange)) == 1


async def test_policy_currency_flags_and_original_rules_remain(client, session, workflow_context):
    _, _, scheme, _, _, _ = workflow_context
    config = await setup_monitor(client, session, workflow_context)
    monitor = await session.get(SourceMonitor, UUID(config["id"]))
    monitor.verification_status = "POTENTIALLY_OUTDATED"
    monitor.enabled = False
    await session.commit()
    detail = (await client.get(f"/api/v1/schemes/{scheme.id}")).json()
    assert detail["eligibility_available"] and detail["policy_currency"] == "POTENTIALLY_OUTDATED"
    report = await client.post(
        "/api/v1/eligibility/check",
        json={"scheme_id": str(scheme.id), "synthetic_profile": True, "profile": {"age_years": 18}},
    )
    assert report.json()["result"] == "PASS" and report.json()["policy_currency"] == "POTENTIALLY_OUTDATED"
