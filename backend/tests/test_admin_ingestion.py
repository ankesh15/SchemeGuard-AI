from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.api.v1.admin_documents import llm_provider
from app.auth.security import PASSWORDS
from app.ingestion.validation import IngestionError
from app.models import (
    AuditEvent,
    DocumentAsset,
    DocumentChunk,
    DocumentPage,
    DocumentVersion,
    LoginSession,
    ProcessingJob,
    RuleCandidate,
    RuleSet,
    Scheme,
    User,
)
from tests.ingestion_support import (
    ORIGIN,
    PASSWORD,
    FixtureProvider,
    approve,
    authenticated,
    candidate_batch,
    pdf_content,
    upload,
)


@pytest.fixture
async def admin_context(client, session, tmp_path):
    app = client._transport.app
    app.state.settings = app.state.settings.model_copy(
        update={"document_storage_root": tmp_path, "gemini_api_key": None}
    )
    administrator, headers = await authenticated(client, session)
    scheme = await session.scalar(select(Scheme).where(Scheme.is_demo.is_(False)).limit(1))
    source_id = await approve(client, headers, scheme.id)
    return app, administrator, headers, scheme, source_id


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/overview"),
        ("GET", "/documents"),
        ("POST", "/documents"),
        ("GET", "/sources"),
        ("POST", "/sources"),
        ("GET", "/audit"),
        ("GET", "/extractions/" + str(uuid4())),
        ("POST", "/documents/" + str(uuid4()) + "/extract"),
    ],
)
async def test_all_ingestion_routes_require_admin(client, method, path):
    response = await client.request(method, "/api/v1/admin" + path, json={})
    assert response.status_code == 401
    assert "no-store" in response.headers["cache-control"]


async def test_citizen_role_cannot_access_workspace(client, session):
    await authenticated(client, session, role="citizen")
    assert (await client.get("/api/v1/admin/documents")).status_code == 403


async def test_account_default_is_least_privilege(session):
    user = User(username="new_" + uuid4().hex[:10], password_hash="not-a-real-password-hash")
    session.add(user)
    await session.flush()
    assert user.role == "citizen"
    assert (
        await session.scalar(
            text(
                "SELECT column_default FROM information_schema.columns WHERE table_name='users' AND column_name='role'"
            )
        )
        == "'citizen'::character varying"
    )


async def test_login_session_csrf_origin_and_logout(client, session):
    username = "login_" + uuid4().hex[:10]
    user = User(username=username, password_hash=PASSWORDS.hash(PASSWORD), role="admin")
    session.add(user)
    await session.commit()
    body = {"username": username, "password": PASSWORD}
    assert (await client.post("/api/v1/admin/auth/login", json=body)).status_code == 403
    assert (
        await client.post("/api/v1/admin/auth/login", json=body | {"password": "wrong"}, headers=ORIGIN)
    ).status_code == 401
    response = await client.post("/api/v1/admin/auth/login", json=body, headers=ORIGIN)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert PASSWORD not in response.text and "password_hash" not in response.text
    raw = client.cookies.get("schemeguard_session")
    stored = await session.scalar(select(LoginSession).where(LoginSession.user_id == user.id))
    assert stored.token_hash != raw and len(stored.token_hash) == 64
    token = response.json()["csrf_token"]
    assert (await client.get("/api/v1/admin/auth/session")).status_code == 200
    assert (await client.post("/api/v1/admin/auth/logout", headers=ORIGIN)).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/auth/logout", headers={"Origin": "https://evil.example", "X-CSRF-Token": token}
        )
    ).status_code == 403
    assert (
        await client.post("/api/v1/admin/auth/logout", headers=ORIGIN | {"X-CSRF-Token": token})
    ).status_code == 204
    assert (await client.get("/api/v1/admin/documents")).status_code == 401
    assert await session.scalar(select(func.count()).select_from(AuditEvent)) >= 3


async def test_expired_and_inactive_sessions_denied(client, session):
    administrator, _ = await authenticated(client, session)
    login = await session.scalar(select(LoginSession).where(LoginSession.user_id == administrator.id))
    login.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    assert (await client.get("/api/v1/admin/overview")).status_code == 401


async def test_login_is_rate_limited(client):
    for _ in range(10):
        assert (
            await client.post(
                "/api/v1/admin/auth/login",
                headers=ORIGIN,
                json={"username": "no_such_user", "password": "bad"},
            )
        ).status_code == 401
    response = await client.post(
        "/api/v1/admin/auth/login", headers=ORIGIN, json={"username": "no_such_user", "password": "bad"}
    )
    assert response.status_code == 429 and response.headers["retry-after"]


async def test_source_authorization_upload_duplicate_versions_and_public_preservation(
    client, session, admin_context
):
    app, administrator, headers, scheme, source_id = admin_context
    before_rules = await session.scalar(select(func.count()).select_from(RuleSet))
    content = pdf_content()
    first = await upload(client, headers, source_id, content)
    assert first.status_code == 201, first.text
    item = first.json()
    assert item["version_number"] == 1 and item["publication_date"] is None
    duplicate = await upload(client, headers, source_id, content)
    assert duplicate.status_code == 200 and duplicate.json()["id"] == item["id"]
    assert duplicate.headers["x-document-duplicate"] == "true"
    second = await upload(client, headers, source_id, pdf_content("Synthetic changed document, 18 years."))
    assert second.status_code == 201 and second.json()["version_number"] == 2
    assert second.json()["supersedes_id"] == item["id"]
    original = await client.get(f"/api/v1/admin/documents/{item['id']}/original")
    assert original.content == content and "attachment" in original.headers["content-disposition"]
    assert (await client.get("/api/v1/admin/documents?page_size=1")).json()["total"] == 2
    assert await session.scalar(select(func.count()).select_from(RuleSet)) == before_rules
    scheme_detail = await client.get(f"/api/v1/schemes/{scheme.id}")
    assert scheme_detail.status_code == 200
    assert not scheme_detail.json()["eligibility_available"]


async def test_upload_limits_actual_contents_attestation_and_unapproved_source(
    client, session, admin_context
):
    app, administrator, headers, scheme, source_id = admin_context
    assert (await upload(client, headers, source_id, b"fake PDF contents")).status_code == 422
    app.state.settings = app.state.settings.model_copy(update={"pdf_max_bytes": 1024})
    assert (await upload(client, headers, source_id, b"x" * 1025)).status_code == 413
    response = await client.post(
        "/api/v1/admin/documents",
        params={"source_id": source_id, "original_filename": "x.pdf"},
        headers=headers | {"Content-Type": "application/pdf"},
        content=pdf_content(),
    )
    assert response.status_code == 422
    assert (await upload(client, headers, uuid4())).status_code == 403
    assert await session.scalar(select(func.count()).select_from(DocumentAsset)) == 0


async def test_authorized_download_uses_exact_registered_url_and_revocation(
    client, session, admin_context, monkeypatch
):
    from app.api.v1 import admin_documents

    app, administrator, headers, scheme, source_id = admin_context
    fetch = AsyncMock(return_value=(pdf_content(), "official.pdf"))
    monkeypatch.setattr(admin_documents, "fetch_pdf", fetch)
    response = await client.post("/api/v1/admin/documents", headers=headers, json={"source_id": source_id})
    assert response.status_code == 201
    assert fetch.call_args.args[0] == "https://scholarships.gov.in/public/test-fixture.pdf"
    assert (
        await client.post(f"/api/v1/admin/sources/{source_id}/revoke", headers=headers)
    ).status_code == 204
    assert (await upload(client, headers, source_id)).status_code == 403


async def test_complete_mock_pipeline_stores_pending_traceable_candidates_only(
    client, session, admin_context
):
    app, administrator, headers, scheme, source_id = admin_context
    app.dependency_overrides[llm_provider] = lambda: FixtureProvider()
    document = (await upload(client, headers, source_id)).json()
    path = f"/api/v1/admin/documents/{document['id']}"
    response = await client.post(path + "/extract", headers=headers, json={"mode": "gemini"})
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "PENDING_REVIEW" and job["candidate_count"] == 1
    candidates = (await client.get(f"/api/v1/admin/extractions/{job['id']}/candidates")).json()["items"]
    assert candidates[0]["review_status"] == "PENDING" and candidates[0]["validation_status"] == "VALIDATED"
    assert candidates[0]["evidence"][0]["page_number"] == 1
    assert (await client.get(path + "/pages/1")).json()["text_content"]
    assert await session.scalar(select(func.count()).select_from(RuleSet)) == 0
    stored = await session.get(ProcessingJob, UUID(job["id"]))
    assert stored.input_manifest and stored.input_chunk_count > 0
    # Retrying preserves immutable pages/chunks; it creates a new extraction job.
    chunks_before = list(await session.scalars(select(DocumentChunk.id)))
    assert (await client.post(path + "/extract", headers=headers, json={"mode": "parse_only"})).json()[
        "status"
    ] == "PARSED"
    assert list(await session.scalars(select(DocumentChunk.id))) == chunks_before
    assert await session.scalar(select(func.count()).select_from(DocumentPage)) == 1
    # Approval is absent from this phase, even through direct SQL updates.
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(text("UPDATE extracted_rule_candidates SET review_status='APPROVED'"))


async def test_missing_key_and_image_only_documents_have_visible_errors(client, session, admin_context):
    app, administrator, headers, scheme, source_id = admin_context
    for content, error_code in [
        (pdf_content(), "gemini_credentials_missing"),
        (pdf_content(text=""), "no_document_text"),
    ]:
        document = (await upload(client, headers, source_id, content)).json()
        job = (
            await client.post(
                f"/api/v1/admin/documents/{document['id']}/extract", headers=headers, json={"mode": "gemini"}
            )
        ).json()
        assert job["status"] == "FAILED", job
        detail = (await client.get(f"/api/v1/admin/extractions/{job['id']}")).json()
        assert error_code in {error["code"] for error in detail["errors"]}
    assert await session.scalar(select(func.count()).select_from(RuleCandidate)) == 0


async def test_failed_provider_rolls_back_all_candidates_but_retains_original_and_parsing(
    client, session, admin_context
):
    app, administrator, headers, scheme, source_id = admin_context

    class WrongDocument(FixtureProvider):
        async def extract(self, context):
            return candidate_batch(context["scheme_id"], uuid4())

    app.dependency_overrides[llm_provider] = lambda: WrongDocument()
    document = (await upload(client, headers, source_id)).json()
    response = await client.post(
        f"/api/v1/admin/documents/{document['id']}/extract", headers=headers, json={"mode": "gemini"}
    )
    assert response.json()["status"] == "FAILED"
    assert await session.scalar(select(func.count()).select_from(RuleCandidate)) == 0
    assert await session.scalar(select(func.count()).select_from(DocumentAsset)) == 1
    assert await session.scalar(select(func.count()).select_from(DocumentPage)) == 1


async def test_batch_relationships_preserved_without_assuming_cross_batch_logic(
    client, session, admin_context
):
    from tests.ingestion_support import TEXT

    app, administrator, headers, scheme, source_id = admin_context

    class AlternativeProvider(FixtureProvider):
        async def extract(self, context):
            batch = await super().extract(context)
            batch.logical_relationship = "or"
            return batch

    app.dependency_overrides[llm_provider] = lambda: AlternativeProvider()
    document = (
        await upload(client, headers, source_id, pdf_content(text="\n".join([TEXT] * 8), pages=16))
    ).json()
    response = await client.post(
        f"/api/v1/admin/documents/{document['id']}/extract", headers=headers, json={"mode": "gemini"}
    )
    assert response.json()["status"] == "PENDING_REVIEW", response.text
    records = list(
        await session.scalars(
            select(RuleCandidate).where(RuleCandidate.job_id == UUID(response.json()["id"]))
        )
    )
    assert len(records) >= 2
    assert {item.logical_relationship for item in records} == {"or"}
    assert all(item.payload["cross_batch_logical_relationship"] == "unspecified" for item in records)
    assert all(item.validation_status == "NEEDS_REVIEW" for item in records)
    assert len({item.condition_identifier for item in records}) == len(records)


async def test_storage_failure_rolls_back_new_document_transaction(
    client, session, admin_context, monkeypatch
):
    from app.ingestion.storage import DocumentStorage

    app, administrator, headers, scheme, source_id = admin_context
    before = await session.scalar(select(func.count()).select_from(DocumentVersion))

    def fail(*args, **kwargs):
        raise IngestionError("test_storage_failure", "Synthetic storage failure", 503)

    monkeypatch.setattr(DocumentStorage, "put", fail)
    response = await upload(client, headers, source_id)
    assert response.status_code == 503
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == before
    assert await session.scalar(select(func.count()).select_from(DocumentAsset)) == 0


async def test_later_batch_failure_keeps_no_partial_candidates(client, session, admin_context):
    from app.ai.provider import ProviderError
    from tests.ingestion_support import TEXT

    app, administrator, headers, scheme, source_id = admin_context

    class FailsLater(FixtureProvider):
        async def extract(self, context):
            if context["batch_number"] > 1:
                raise ProviderError("synthetic_late_failure", "Synthetic later-batch failure")
            return await super().extract(context)

    app.dependency_overrides[llm_provider] = lambda: FailsLater()
    document = (
        await upload(client, headers, source_id, pdf_content(text="\n".join([TEXT] * 8), pages=16))
    ).json()
    job = (
        await client.post(
            f"/api/v1/admin/documents/{document['id']}/extract", headers=headers, json={"mode": "gemini"}
        )
    ).json()
    assert job["status"] == "FAILED"
    assert await session.scalar(select(func.count()).select_from(RuleCandidate)) == 0
    assert await session.scalar(select(func.count()).select_from(DocumentPage)) == 16
    stored = await session.get(ProcessingJob, UUID(job["id"]))
    assert len(stored.input_manifest) >= 2


async def test_chunk_cannot_reference_a_different_documents_page(client, session, admin_context):
    app, administrator, headers, scheme, source_id = admin_context
    first = (await upload(client, headers, source_id)).json()
    second = (
        await upload(client, headers, source_id, pdf_content("A separate synthetic policy document."))
    ).json()
    await client.post(
        f"/api/v1/admin/documents/{first['id']}/extract", headers=headers, json={"mode": "parse_only"}
    )
    first_page = await session.scalar(
        select(DocumentPage).where(DocumentPage.document_version_id == UUID(first["id"]))
    )
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            session.add(
                DocumentChunk(
                    id=uuid4(),
                    document_version_id=UUID(second["id"]),
                    page_id=first_page.id,
                    page_number=1,
                    ordinal=0,
                    section_identifier="test",
                    text_content="wrong source",
                    content_sha256="a" * 64,
                    char_start=0,
                    char_end=12,
                    extraction_method="synthetic-test",
                )
            )
            await session.flush()
