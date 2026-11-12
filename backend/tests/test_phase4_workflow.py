"""Simulated review in disposable PostgreSQL. No real government policy approval."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.graph import WorkflowRunner
from app.api.v1.admin_workflows import get_embeddings
from app.models import RulePublication, RuleSet, Scheme
from app.rag.embeddings import LocalHashEmbeddings
from tests.ingestion_support import FixtureProvider, approve, authenticated, upload


@pytest.fixture
async def workflow_context(client, session, tmp_path):
    app = client._transport.app
    settings = app.state.settings.model_copy(
        update={"document_storage_root": tmp_path, "gemini_api_key": None}
    )
    app.state.settings = settings
    sessions = async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    app.state.workflow_runner = WorkflowRunner(settings, sessions, FixtureProvider())
    app.dependency_overrides[get_embeddings] = lambda: LocalHashEmbeddings()
    administrator, headers = await authenticated(client, session)
    scheme = await session.scalar(select(Scheme).where(Scheme.is_demo.is_(False)).limit(1))
    source_id = await approve(client, headers, scheme.id)
    uploaded = await upload(client, headers, source_id)
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    body = {"document_version_id": document["id"], "request_key": str(uuid4())}
    response = await client.post("/api/v1/admin/workflows", headers=headers, json=body)
    assert response.status_code == 201, response.text
    workflow = response.json()
    if workflow["status"] != "PENDING_REVIEW":
        details = await client.get(f"/api/v1/admin/workflows/{workflow['id']}")
        pytest.fail(details.text)
    return app, headers, scheme, document, workflow, body


async def review_detail(client, workflow):
    response = await client.get(f"/api/v1/admin/reviews/{workflow['review_id']}")
    assert response.status_code == 200, response.text
    return response.json()


async def corrected_review(client, headers, workflow):
    review = await review_detail(client, workflow)
    draft = deepcopy(review["draft"])
    draft.update(
        effective_from="2020-01-01",
        effective_date_basis="reviewer_activation",
        effective_date_note="Simulated administrative activation for isolated synthetic tests only.",
        applicability_note="Complete synthetic age-only fixture; not a real government policy.",
        scope_note="All conditions in the single-page synthetic test fixture are represented.",
    )
    response = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/revisions",
        headers=headers,
        json={
            "expected_revision": 1,
            "draft": draft,
            "notes": "Simulated correction of dates and completeness in an isolated test.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def approval_body(review):
    return {
        "expected_revision": review["revision_number"],
        "proposal_sha256": review["proposal_sha256"],
        "notes": "Simulated human review for automated tests only. Not real policy approval.",
        "human_review_confirmed": True,
        "complete_policy_confirmed": True,
        "applicability_confirmed": True,
        "reviewed_pages": [1],
        "acknowledged_findings": review["required_finding_ids"],
    }


async def test_graph_interrupt_checkpoint_revision_resume_publication(client, session, workflow_context):
    app, headers, scheme, document, workflow, body = workflow_context
    assert workflow["thread_id"] == workflow["id"] and workflow["provider"] == "fixture"
    assert (
        await session.scalar(
            text("SELECT count(*) FROM sg_checkpoints.checkpoints WHERE thread_id=:id"),
            {"id": workflow["id"]},
        )
        >= 5
    )
    original = await review_detail(client, workflow)
    assert not original["validation"]["publishable"]
    # An incomplete extraction cannot be approved by merely checking attestations.
    denied = await client.post(
        f"/api/v1/admin/reviews/{original['id']}/approve", headers=headers, json=approval_body(original)
    )
    assert denied.status_code == 422
    assert (await client.post("/api/v1/admin/workflows", headers=headers, json=body)).json()[
        "id"
    ] == workflow["id"]
    review = await corrected_review(client, headers, workflow)
    assert review["validation"]["publishable"], review["validation"]
    assert review["original_proposal"] == original["original_proposal"]
    # A fresh runner reads persisted checkpoints rather than Python memory.
    app.state.workflow_runner = WorkflowRunner(
        app.state.settings, app.state.workflow_runner.sessions, FixtureProvider()
    )
    approved = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["workflow"]["status"] == "APPROVED", approved.text
    published = approved.json()["workflow"]["published_rule_set_id"]
    duplicate = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
    )
    assert duplicate.status_code == 409
    assert await session.scalar(select(func.count()).select_from(RulePublication)) == 1
    for profile, result in [({"age_years": 18}, "PASS"), ({"age_years": 17}, "FAIL"), ({}, "UNKNOWN")]:
        report = await client.post(
            "/api/v1/eligibility/explain",
            json={"scheme_id": str(scheme.id), "synthetic_profile": True, "profile": profile},
        )
        assert report.status_code == 200, report.text
        data = report.json()
        assert data["report"]["result"] == data["explanation"]["result"] == result
        assert data["report"]["rule_set"]["id"] == published
        assert data["explanation"]["citations"][0]["page_number"] == 1
    index = await client.post(f"/api/v1/admin/documents/{document['id']}/index", headers=headers)
    assert index.status_code == 200, index.text
    question = await client.post(
        f"/api/v1/schemes/{scheme.id}/questions", json={"question": "What are the eligibility requirements?"}
    )
    assert question.status_code == 200, question.text
    assert question.json()["citations"][0]["document_version_id"] == document["id"]
    assert question.json()["retrieval_mode"] == "local_fixture_vector"
    assert (await client.get(f"/api/v1/schemes/{scheme.id}/rule-history")).json()["items"][0][
        "id"
    ] == published
    # Idempotent terminal resume does not create another version.
    assert (
        await client.post(
            f"/api/v1/admin/workflows/{workflow['id']}/resume",
            headers=headers,
            json={"notes": "Verify idempotent terminal workflow recovery in isolated tests."},
        )
    ).status_code == 200
    assert await session.scalar(select(func.count()).select_from(RulePublication)) == 1


async def test_rejection_and_cancellation(client, session, workflow_context):
    app, headers, scheme, document, workflow, _ = workflow_context
    review = await review_detail(client, workflow)
    response = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/reject",
        headers=headers,
        json={
            "expected_revision": 1,
            "notes": "Simulated rejection: incomplete policy evidence cannot be published.",
        },
    )
    assert response.status_code == 200 and response.json()["workflow"]["status"] == "REJECTED", response.text
    assert not await session.scalar(select(RulePublication.id))
    response = await client.post(
        "/api/v1/admin/workflows",
        headers=headers,
        json={
            "document_version_id": document["id"],
            "extraction_job_id": workflow["extraction_job_id"],
            "request_key": str(uuid4()),
        },
    )
    second = response.json()
    cancelled = await client.post(
        f"/api/v1/admin/workflows/{second['id']}/cancel",
        headers=headers,
        json={"notes": "Simulated cancellation of an undecided policy review in tests."},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED", cancelled.text
    resumed = await client.post(
        f"/api/v1/admin/workflows/{second['id']}/resume",
        headers=headers,
        json={"notes": "Attempt to resume the cancelled workflow should be rejected."},
    )
    assert resumed.status_code == 409


@pytest.mark.parametrize(
    "path,method",
    [
        ("workflows", "GET"),
        ("workflows", "POST"),
        (f"workflows/{uuid4()}", "GET"),
        ("reviews", "GET"),
        (f"reviews/{uuid4()}/approve", "POST"),
        (f"reviews/{uuid4()}/reject", "POST"),
    ],
)
async def test_workflow_authorization(client, path, method):
    assert (await client.request(method, f"/api/v1/admin/{path}", json={})).status_code == 401


async def test_stale_digest_csrf_pages_and_immutable_revisions(client, session, workflow_context):
    from sqlalchemy.exc import DBAPIError

    app, headers, scheme, document, workflow, _ = workflow_context
    review = await corrected_review(client, headers, workflow)
    path = f"/api/v1/admin/reviews/{review['id']}/approve"
    assert (await client.post(path, json=approval_body(review))).status_code == 403
    for change, status in [
        ({"proposal_sha256": "f" * 64}, 409),
        ({"expected_revision": 1}, 409),
        ({"human_review_confirmed": False}, 422),
        ({"reviewed_pages": [2]}, 422),
        ({"acknowledged_findings": []}, 422),
    ]:
        response = await client.post(path, headers=headers, json=approval_body(review) | change)
        assert response.status_code == status, response.text
    for table, assignment, column in [
        ("review_revisions", "notes='forged history'", "review_id"),
        ("policy_reviews", "original_proposal='{}'::jsonb", "id"),
    ]:
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text(f"UPDATE {table} SET {assignment} WHERE {column}=:id"), {"id": UUID(review["id"])}
                )
    assert not await session.scalar(select(RulePublication.id))


async def test_contradictions_evidence_scope_and_rollbacks(client, session, workflow_context):
    app, headers, scheme, document, workflow, _ = workflow_context
    review = await corrected_review(client, headers, workflow)
    draft = deepcopy(review["draft"])
    condition = deepcopy(draft["conditions"][0])
    condition.update(key="contradiction", source_candidate_id=None)
    condition["expression"].update(key="contradiction", operator="<")
    condition["evidence"][0]["node_key"] = "contradiction"
    draft["conditions"].append(condition)
    response = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/revisions",
        headers=headers,
        json={
            "expected_revision": 2,
            "draft": draft,
            "notes": "Simulated contradictory revision retained for correction only.",
        },
    )
    assert response.status_code == 201
    invalid = response.json()
    assert not invalid["validation"]["publishable"]
    assert any("contradictory" in error for error in invalid["validation"]["errors"])
    assert (
        await client.post(
            f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(invalid)
        )
    ).status_code == 422
    assert not await session.scalar(select(RulePublication.id))
    assert not (await client.get(f"/api/v1/schemes/{scheme.id}/rule-history")).json()["items"]
    explanation = await client.post(
        "/api/v1/eligibility/explain",
        json={"scheme_id": str(scheme.id), "synthetic_profile": True, "profile": {}},
    )
    assert explanation.json()["report"]["result"] == "UNKNOWN"
    assert "No effective approved policy" in explanation.json()["explanation"]["summary"]
    assert not explanation.json()["explanation"]["citations"]
    unanswered = await client.post(
        f"/api/v1/schemes/{scheme.id}/questions", json={"question": "What are the eligibility requirements?"}
    )
    assert not unanswered.json()["citations"]
    assert "does not establish" in unanswered.json()["answer"]


async def test_embedding_failure_and_cross_scheme_retrieval(client, session, workflow_context):
    from app.agents.explanation_agent import ExplanationPlan, explain_assessment
    from app.models import ChunkEmbedding
    from app.rag.embeddings import EmbeddingError, index_document
    from app.rag.retriever import retrieve_for_rule
    from app.repositories.rule import RuleRepository
    from app.repositories.scheme import SchemeRepository
    from app.schemas.eligibility import EligibilityRequest
    from app.services.eligibility import EligibilityService

    app, headers, scheme, document, workflow, _ = workflow_context
    review = await corrected_review(client, headers, workflow)
    approved = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
    )
    rule_id = UUID(approved.json()["workflow"]["published_rule_set_id"])

    class FailedEmbeddings:
        name = "gemini"
        model = "failure-fixture"

        async def embed(self, texts, *, query=False):
            raise EmbeddingError("embedding_provider_unavailable")

    with pytest.raises(EmbeddingError):
        await index_document(session, UUID(document["id"]), FailedEmbeddings(), app.state.settings)
    await session.refresh(scheme)
    assert not await session.scalar(select(ChunkEmbedding.id))
    citations, mode = await retrieve_for_rule(
        session, app.state.settings, FailedEmbeddings(), scheme.id, rule_id, "applicant age"
    )
    assert mode == "lexical_fallback" and citations[0].page_number == 1
    unrelated = uuid4()
    assert (
        await retrieve_for_rule(session, app.state.settings, LocalHashEmbeddings(), unrelated, rule_id, "age")
    )[0] == []
    assert (
        await retrieve_for_rule(
            session,
            app.state.settings,
            LocalHashEmbeddings(),
            scheme.id,
            rule_id,
            "age",
            document_version_id=uuid4(),
        )
    )[0] == []
    report = await EligibilityService(SchemeRepository(session), RuleRepository(session)).check(
        EligibilityRequest(scheme_id=scheme.id, synthetic_profile=True, profile={"age_years": 17})
    )

    class MaliciousPlan:
        async def plan(self, context):
            return ExplanationPlan(trace_order=["fabricated-PASS"], citation_ids=["invented-source"])

    explained = await explain_assessment(
        session,
        app.state.settings.model_copy(update={"explanation_use_gemini": True}),
        FailedEmbeddings(),
        report,
        MaliciousPlan(),
    )
    assert explained["result"] == "FAIL" and explained["mode"] == "deterministic_template"
    assert explained["failed_conditions"] and all(
        item["id"] != "invented-source" for item in explained["citations"]
    )


async def test_overlapping_approved_version_requires_explicit_review(client, session, workflow_context):
    app, headers, scheme, document, workflow, _ = workflow_context
    review = await corrected_review(client, headers, workflow)
    first = (
        await client.post(
            f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
        )
    ).json()
    original_rule_id = first["workflow"]["published_rule_set_id"]
    new = (
        await client.post(
            "/api/v1/admin/workflows",
            headers=headers,
            json={
                "document_version_id": document["id"],
                "extraction_job_id": workflow["extraction_job_id"],
                "request_key": str(uuid4()),
            },
        )
    ).json()
    second = await corrected_review(client, headers, new)
    assert (
        not second["validation"]["publishable"]
        and second["validation"]["overlapping_rule_sets"][0]["id"] == original_rule_id
    )
    second["draft"].update(
        replaces_rule_set_ids=[original_rule_id],
        replacement_notes="Simulated same-scope activation replacement in isolated test, retaining historical version.",
    )
    revised = (
        await client.post(
            f"/api/v1/admin/reviews/{second['id']}/revisions",
            headers=headers,
            json={
                "expected_revision": 2,
                "draft": second["draft"],
                "notes": "Reviewed overlapping synthetic policy date and applicability relationship.",
            },
        )
    ).json()
    assert revised["validation"]["publishable"]
    approved = await client.post(
        f"/api/v1/admin/reviews/{second['id']}/approve", headers=headers, json=approval_body(revised)
    )
    assert approved.json()["workflow"]["status"] == "APPROVED", approved.text
    history = (await client.get(f"/api/v1/schemes/{scheme.id}/rule-history")).json()["items"]
    assert [item["version_number"] for item in history] == [2, 1]
    assert history[0]["reviewed_replacement_ids"] == [original_rule_id]
    assert history[1]["id"] == original_rule_id


async def test_missing_gemini_workflow_can_recover_without_fake_approval(client, session, workflow_context):
    app, headers, scheme, document, workflow, _ = workflow_context
    from app.ai.provider import GeminiProvider

    app.state.workflow_runner = WorkflowRunner(
        app.state.settings, app.state.workflow_runner.sessions, GeminiProvider(app.state.settings)
    )
    response = await client.post(
        "/api/v1/admin/workflows",
        headers=headers,
        json={"document_version_id": document["id"], "request_key": str(uuid4())},
    )
    failed = response.json()
    assert failed["status"] == "FAILED" and failed["error_code"]
    assert not failed["published_rule_set_id"]
    app.state.workflow_runner = WorkflowRunner(
        app.state.settings, app.state.workflow_runner.sessions, FixtureProvider()
    )
    resumed = await client.post(
        f"/api/v1/admin/workflows/{failed['id']}/resume",
        headers=headers,
        json={"notes": "Retry after restoring an explicitly injected synthetic fixture provider."},
    )
    assert resumed.status_code == 200 and resumed.json()["status"] == "PENDING_REVIEW", resumed.text
    assert not await session.scalar(select(RulePublication.id))


async def test_publication_transaction_rollback_and_recovery(client, session, workflow_context, monkeypatch):
    import app.agents.publisher as publisher
    from app.models import ReviewDecision

    app, headers, scheme, document, workflow, _ = workflow_context
    review = await corrected_review(client, headers, workflow)
    original = publisher.RuleEvidence

    def fail_after_draft_insert(**kwargs):
        raise ValueError("Synthetic failure after inserting draft and condition")

    monkeypatch.setattr(publisher, "RuleEvidence", fail_after_draft_insert)
    response = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=headers, json=approval_body(review)
    )
    assert response.status_code == 200 and response.json()["workflow"]["status"] == "FAILED", response.text
    assert not await session.scalar(select(RuleSet.id).where(RuleSet.scheme_id == scheme.id))
    assert not await session.scalar(select(RulePublication.id))
    assert await session.scalar(select(ReviewDecision.action)) == "APPROVE"
    monkeypatch.setattr(publisher, "RuleEvidence", original)
    response = await client.post(
        f"/api/v1/admin/workflows/{workflow['id']}/resume",
        headers=headers,
        json={"notes": "Resume exact simulated approval after resolving the injected transactional failure."},
    )
    assert response.status_code == 200 and response.json()["status"] == "APPROVED", response.text
    assert await session.scalar(select(func.count()).select_from(RulePublication)) == 1
