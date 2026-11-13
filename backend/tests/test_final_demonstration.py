"""A/B/C end-to-end demonstration in a disposable database; every policy change is fictional."""

import json
from time import perf_counter
from uuid import uuid4

from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.ingestion.pdf_parser import parse_pdf
from app.models import DocumentVersion, Notification, RuleSet
from app.services.reassessment import reassess_change
from tests.ingestion_support import TEXT, FixtureProvider, pdf_content
from tests.test_citizen import signup
from tests.test_monitoring import setup_monitor
from tests.test_phase4_workflow import workflow_context as workflow_context
from tests.test_reassessment import publish_update


async def test_complete_synthetic_workflows(client, session, workflow_context, monkeypatch):
    app, admin_headers, scheme, document, workflow, _ = workflow_context
    app.state.settings = app.state.settings.model_copy(
        update={"profile_encryption_key": SecretStr(Fernet.generate_key().decode())}
    )
    metrics = {}

    async def timed(name, action):
        start = perf_counter()
        result = await action
        metrics[name] = round((perf_counter() - start) * 1000, 3)
        return result

    await timed(
        "pdf_processing_ms", parse_pdf(pdf_content(TEXT), max_pages=5, max_chars=20000, timeout_seconds=10)
    )
    await timed(
        "mock_ai_extraction_ms",
        FixtureProvider().extract({"scheme_id": str(scheme.id), "source_document_version": document["id"]}),
    )
    assert workflow["status"] == "PENDING_REVIEW"
    config = await timed(
        "administrator_review_publication_ms", setup_monitor(client, session, workflow_context)
    )
    index = await client.post(f"/api/v1/admin/documents/{document['id']}/index", headers=admin_headers)
    assert index.status_code == 200, index.text
    answer = await timed(
        "rag_retrieval_ms",
        client.post(
            f"/api/v1/schemes/{scheme.id}/questions",
            json={"question": "What are the eligibility requirements?"},
        ),
    )
    citations = answer.json()["citations"]
    assert (
        citations
        and citations[0]["page_number"] == 1
        and citations[0]["document_version_id"] == document["id"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as citizen:
        _, headers = await signup(citizen)
        assert (
            await citizen.put("/api/v1/profiles/me", headers=headers, json={"age_years": 18})
        ).status_code == 200
        discovery = await timed(
            "scheme_search_ms", citizen.get("/api/v1/schemes?search=Scholarship&page_size=6")
        )
        assert discovery.status_code == 200
        saved = await timed(
            "evaluation_and_save_ms",
            citizen.post(
                "/api/v1/assessments",
                headers=headers,
                json={"scheme_id": str(scheme.id), "request_key": str(uuid4()), "allow_reassessment": True},
            ),
        )
        assert saved.status_code == 201, saved.text
        old = saved.json()
        assert old["result"] == "PASS" and old["report"]["requirements"][0]["evidence"]
        change = await timed(
            "monitor_parse_graph_compare_review_ms",
            publish_update(client, session, workflow_context, config, monkeypatch),
        )
        outcome = await timed(
            "background_reassessment_ms", reassess_change(session, app.state.settings, change.id)
        )
        assert outcome["reassessed"] == outcome["notified"] == 1
        history = (await citizen.get("/api/v1/assessments")).json()
        assert {item["result"] for item in history["items"]} == {"PASS", "FAIL"}
        assert (await citizen.post(f"/api/v1/assessments/{old['id']}/reproduce", headers=headers)).json()[
            "matches_original"
        ]
        assert (await citizen.get("/api/v1/notifications")).json()["unread_count"] == 1
        assert (await reassess_change(session, app.state.settings, change.id))["reassessed"] == 0
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 2
    assert await session.scalar(select(func.count()).select_from(RuleSet)) == 2
    assert await session.scalar(select(func.count()).select_from(Notification)) == 1
    print(
        "PHASE7_DEMONSTRATION="
        + json.dumps(
            {
                "workflows": {
                    "A": "PASS: source/PDF/mock AI/LangGraph/simulated human approval/publication",
                    "B": "PASS: private profile/discovery/approved evaluation/evidence/saved report",
                    "C": "PASS: changed PDF/comparison/review/new version/reassessment/notification",
                },
                "measurements_ms": metrics,
                "sample_count": 1,
                "external_AI": "mocked, not a Gemini latency/accuracy measurement",
                "human_review": "simulated exact-revision decision, not real government approval",
                "database": "disposable PostgreSQL; fixtures and all private data are rolled back",
                "documents_preserved": 2,
                "approved_fixture_versions": 2,
                "deduplicated_notifications": 1,
            }
        )
    )
