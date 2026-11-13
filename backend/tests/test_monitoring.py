from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.ingestion.fetcher import FetchResponse, safe_validator
from app.ingestion.validation import IngestionError
from app.models import (
    BackgroundJob,
    DocumentVersion,
    MonitoringRun,
    PolicyChange,
    PolicyChangeDetail,
    RulePublication,
    SourceMonitor,
)
from app.services.jobs import claim, enqueue
from app.services.monitoring import (
    compare_change,
    monitor_document,
    next_check,
    process_change_document,
    schedule_due,
)
from app.services.policy_diff import compare_document_facts, compare_policies
from tests.ingestion_support import TEXT, FixtureProvider, candidate_batch, pdf_content
from tests.test_phase4_workflow import approval_body, corrected_review
from tests.test_phase4_workflow import workflow_context as workflow_context


def condition(value, **changes):
    return {
        "key": "income",
        "label": "Synthetic income",
        "expression": {
            "kind": "comparison",
            "key": "c0_income",
            "field": "annual_family_income_inr",
            "operator": "<=",
            "value_type": "number",
            "value": value,
            **changes,
        },
        "evidence": [{"page_number": 1, "excerpt": f"Synthetic annual INR income maximum {value}."}],
    }


@pytest.mark.parametrize(
    "old,new,kind", [(250000, 300000, "THRESHOLD_INCREASED"), (300000, 250000, "THRESHOLD_DECREASED")]
)
def test_threshold_diff(old, new, kind):
    classification, details = compare_policies([condition(old)], [condition(new)], complete=True)
    assert classification == "MATERIAL" and details[0]["change_type"] == kind
    assert details[0]["verification_status"] == "PENDING_REVIEW"
    assert details[0]["old_evidence"] and details[0]["new_evidence"]


def test_inconclusive_removals_and_wording():
    assert compare_policies([condition(250000)], [])[0] == "INCONCLUSIVE"
    assert (
        compare_policies([condition(250000)], [condition(250000) | {"label": "Different wording"}])[0]
        == "WORDING"
    )
    assert (
        compare_policies([], [{"key": "documents", "expression": None, "evidence": []}])[0] == "INCONCLUSIVE"
    )


def test_explicit_deadlines_and_documents():
    before = [
        {
            "document_version_id": "old",
            "page_number": 1,
            "text": "Application deadline: 2026-12-01\nRequired documents: Enrollment certificate",
        }
    ]
    after = [
        {
            "document_version_id": "new",
            "page_number": 2,
            "text": "Application deadline: 2026-12-15\nRequired documents: Enrollment certificate, income certificate",
        }
    ]
    details = compare_document_facts(before, after)
    assert {item["change_type"] for item in details} == {
        "APPLICATION_DEADLINE_CHANGED",
        "REQUIRED_DOCUMENTS_CHANGED",
    }
    assert all(item["new_evidence"][0]["page_number"] == 2 for item in details)
    assert all(not item["executable"] for item in details)
    assert compare_document_facts(before, [])[0]["change_type"] == "INCONCLUSIVE_DOCUMENT_FACT"


def test_schedule_and_validator_security():
    now = datetime(2026, 11, 13, 4, tzinfo=UTC)
    monitor = SourceMonitor(frequency="daily", hour_utc=3, weekday=0, min_interval_seconds=60)
    assert next_check(monitor, now) == datetime(2026, 11, 14, 3, tzinfo=UTC)
    monitor.frequency = "weekly"
    assert next_check(monitor, now).weekday() == 0
    assert safe_validator('"abc"') == '"abc"'
    assert safe_validator("evil\r\nHeader: value") is None


async def test_durable_claim_deduplication_and_crash_lease(session, test_settings):
    key = "test:" + str(uuid4())
    identifier = await enqueue(session, "PROBE", key, {})
    assert await enqueue(session, "PROBE", key, {}) == identifier
    await session.commit()
    first = await claim(session, identifier, 4, 600)
    assert first and first.attempts == 1
    assert await claim(session, identifier, 4, 600) is None
    first = await session.get(BackgroundJob, identifier)
    first.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    again = await claim(session, identifier, 4, 600)
    assert again.attempts == 2


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "monitors"),
        ("POST", "monitors"),
        ("PATCH", f"monitors/{uuid4()}"),
        ("POST", f"monitors/{uuid4()}/check"),
        ("GET", "monitoring-runs"),
        ("GET", "policy-changes"),
        ("POST", f"policy-changes/{uuid4()}/approve"),
    ],
)
async def test_monitor_admin_authorization(client, method, path):
    assert (await client.request(method, "/api/v1/admin/" + path, json={})).status_code == 401


async def setup_monitor(client, session, context):
    app, headers, scheme, document, workflow, _ = context
    review = await corrected_review(client, headers, workflow)
    published = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
    )
    assert published.json()["workflow"]["status"] == "APPROVED"
    response = await client.post(
        "/api/v1/admin/monitors",
        headers=headers,
        json={
            "source_id": document["source_id"],
            "enabled": True,
            "frequency": "daily",
            "access_permitted": True,
            "access_notes": "Synthetic isolated source permits this scheduled test access.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_unchanged_detection_and_formatting_avoids_ai(client, session, workflow_context, monkeypatch):
    app, headers, scheme, document, workflow, _ = workflow_context
    config = await setup_monitor(client, session, workflow_context)
    original = (await client.get(f"/api/v1/admin/documents/{document['id']}/original")).content
    response = await client.post(f"/api/v1/admin/monitors/{config['id']}/check", headers=headers)
    assert response.status_code == 202, response.text
    job = await session.get(BackgroundJob, UUID(response.json()["job_id"]))
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(return_value=FetchResponse(200, original, "synthetic.pdf", '"v1"', None)),
    )
    result = await monitor_document(session, app.state.settings, job)
    assert result["status"] == "UNCHANGED"
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 1
    monitor = await session.get(SourceMonitor, UUID(config["id"]))
    monitor.last_started_at = datetime.now(UTC) - timedelta(seconds=4000)
    monitor.next_check_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    assert await schedule_due(session) == 1
    job = await session.scalar(
        select(BackgroundJob).where(BackgroundJob.status == "QUEUED", BackgroundJob.id != job.id)
    )
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(return_value=FetchResponse(200, pdf_content(TEXT), "synthetic.pdf")),
    )
    result = await monitor_document(session, app.state.settings, job)
    assert result["status"] == "CHANGED"
    docjob = await session.scalar(select(BackgroundJob).where(BackgroundJob.kind == "DOCUMENT"))
    parsed = await process_change_document(session, app.state.settings, docjob, app.state.workflow_runner)
    assert parsed["ai_skipped"] and parsed["classification"] == "FORMATTING"
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 2


async def test_material_change_reuses_graph_and_human_approval(
    client, session, workflow_context, monkeypatch
):
    from app.agents.graph import WorkflowRunner

    app, headers, scheme, document, workflow, _ = workflow_context
    config = await setup_monitor(client, session, workflow_context)
    job_id = (await client.post(f"/api/v1/admin/monitors/{config['id']}/check", headers=headers)).json()[
        "job_id"
    ]
    job = await session.get(BackgroundJob, UUID(job_id))
    new_text = TEXT.replace("18", "19")
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(return_value=FetchResponse(200, pdf_content(new_text), "new-synthetic.pdf")),
    )
    assert (await monitor_document(session, app.state.settings, job))["status"] == "CHANGED"

    class NewFixture(FixtureProvider):
        async def extract(self, context):
            batch = candidate_batch(context["scheme_id"], context["source_document_version"])
            batch.candidates[0].nodes[0].expected_value = 19
            batch.candidates[0].evidence[0].supporting_excerpt = new_text
            return batch

    runner = WorkflowRunner(app.state.settings, app.state.workflow_runner.sessions, NewFixture())
    app.state.workflow_runner = runner
    docjob = await session.scalar(select(BackgroundJob).where(BackgroundJob.kind == "DOCUMENT"))
    await process_change_document(session, app.state.settings, docjob, runner)
    change = await session.scalar(select(PolicyChange))
    await compare_change(session, change.id)
    await session.commit()
    assert change.classification == "MATERIAL"
    detail = await session.scalar(select(PolicyChangeDetail))
    assert detail.detail["change_type"] == "THRESHOLD_INCREASED"
    assert (await client.get("/api/v1/policy-updates")).json()["items"] == []
    pending = (await client.get(f"/api/v1/admin/workflows/{change.workflow_id}")).json()
    review = await corrected_review(client, headers, pending)
    review["draft"].update(
        replaces_rule_set_ids=[str(change.old_rule_set_id)],
        replacement_notes="Simulated same-applicability policy replacement, retaining immutable historical rule.",
    )
    review = (
        await client.post(
            f"/api/v1/admin/reviews/{review['id']}/revisions",
            headers=headers,
            json={
                "expected_revision": 2,
                "draft": review["draft"],
                "notes": "Simulated complete review of the old and new source-supported age policies.",
            },
        )
    ).json()
    approved = await client.post(
        f"/api/v1/admin/policy-changes/{change.id}/approve", headers=headers, json=approval_body(review)
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["verification_status"] == "APPROVED", approved.text
    assert len((await client.get("/api/v1/policy-updates")).json()["items"]) == 1
    report = await client.post(
        "/api/v1/eligibility/check",
        json={"scheme_id": str(scheme.id), "synthetic_profile": True, "profile": {"age_years": 18}},
    )
    assert report.json()["result"] == "FAIL"
    assert await session.scalar(select(func.count()).select_from(RulePublication)) == 2
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 2


async def test_worker_retry_invalid_content_and_duplicate_delivery(
    client, session, workflow_context, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.workers.monitoring_tasks import execute_job

    app, headers, scheme, document, workflow, _ = workflow_context
    config = await setup_monitor(client, session, workflow_context)
    identifier = UUID(
        (await client.post(f"/api/v1/admin/monitors/{config['id']}/check", headers=headers)).json()["job_id"]
    )
    factory = async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(side_effect=IngestionError("download_timeout", "Synthetic transient timeout", 504)),
    )
    assert await execute_job(identifier, settings=app.state.settings, sessions=factory) == "RETRY"
    job = await session.get(BackgroundJob, identifier, populate_existing=True)
    assert job.attempts == 1 and job.available_at > datetime.now(UTC)
    assert await execute_job(identifier, settings=app.state.settings, sessions=factory) == "SKIPPED"
    job.available_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    monkeypatch.setattr(
        "app.services.monitoring.fetch_pdf_response",
        AsyncMock(return_value=FetchResponse(200, b"not a PDF", "bad.pdf")),
    )
    assert await execute_job(identifier, settings=app.state.settings, sessions=factory) == "FAILED"
    assert await execute_job(identifier, settings=app.state.settings, sessions=factory) == "SKIPPED"
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 1


async def test_policy_clarification_requires_new_revision_and_rejection(client, session, workflow_context):
    app, headers, scheme, document, workflow, _ = workflow_context
    monitor = SourceMonitor(
        source_id=UUID(document["source_id"]),
        created_by=UUID((await client.get("/api/v1/admin/auth/session")).json()["user_id"]),
        enabled=True,
        access_notes="Synthetic source access approval for isolated review tests.",
    )
    session.add(monitor)
    await session.flush()
    job = BackgroundJob(kind="MONITOR", dedupe_key=str(uuid4()), payload={}, status="SUCCEEDED")
    session.add(job)
    await session.flush()
    run = MonitoringRun(
        monitor_id=monitor.id, job_id=job.id, status="CHANGED", new_document_id=UUID(document["id"])
    )
    session.add(run)
    await session.flush()
    change = PolicyChange(
        scheme_id=scheme.id,
        source_id=monitor.source_id,
        run_id=run.id,
        new_document_id=UUID(document["id"]),
        workflow_id=UUID(workflow["id"]),
    )
    session.add(change)
    await session.commit()
    response = await client.post(
        f"/api/v1/admin/policy-changes/{change.id}/clarify",
        headers=headers,
        json={"notes": "Verify all effective dates and source exceptions before publishing."},
    )
    assert response.status_code == 200 and response.json()["verification_status"] == "CLARIFICATION"
    from tests.test_phase4_workflow import review_detail

    review = await review_detail(client, workflow)
    approval = await client.post(
        f"/api/v1/admin/policy-changes/{change.id}/approve", headers=headers, json=approval_body(review)
    )
    assert approval.status_code == 409
    review = await corrected_review(client, headers, workflow)
    response = await client.post(
        f"/api/v1/admin/policy-changes/{change.id}/reject",
        headers=headers,
        json={
            "expected_revision": review["revision_number"],
            "notes": "Synthetic policy rejected after clarification; preserve the previous approved policy.",
        },
    )
    assert response.status_code == 200 and response.json()["verification_status"] == "REJECTED", response.text
    assert not await session.scalar(select(RulePublication.id))


def test_numeric_representation_does_not_invent_policy_change():
    assert compare_policies([condition(250000)], [condition("250000.00")], complete=True)[0] in {
        "FORMATTING",
        "WORDING",
    }
