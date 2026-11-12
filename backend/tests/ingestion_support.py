"""Synthetic policy fixtures; none represent government eligibility."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pymupdf

from app.ai.schemas import CandidateBatch
from app.auth.security import PASSWORDS, Administrator, csrf_token, digest
from app.models import LoginSession, User

TEXT = "Synthetic policy only. Applicant age must be at least 18 years."
ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "Synthetic-fixture-password-78!"


def pdf_content(text=TEXT, pages=1):
    with pymupdf.open() as pdf:
        for _ in range(pages):
            page = pdf.new_page()
            if text:
                page.insert_text((50, 50), text)
        return pdf.tobytes()


def candidate_batch(scheme=None, document=None, **changes):
    payload = {
        "scheme_id": str(scheme or uuid4()),
        "source_document_version": str(document or uuid4()),
        "logical_relationship": "and",
        "limitations": [],
        "candidates": [
            {
                "condition_identifier": "synthetic_age",
                "label": "Synthetic age condition",
                "root": "age",
                "nodes": [
                    {
                        "key": "age",
                        "kind": "comparison",
                        "field": "age_years",
                        "operator": ">=",
                        "expected_value": 18,
                        "value_type": "number",
                        "units": "years",
                    }
                ],
                "evidence": [{"node_key": "age", "source_page": 1, "supporting_excerpt": TEXT}],
                "extraction_uncertainty": [],
            }
        ],
    }
    payload.update(changes)
    return CandidateBatch.model_validate(payload)


class FixtureProvider:
    name = "fixture"
    model: str | None = "synthetic-test"

    async def extract(self, context):
        return candidate_batch(context["scheme_id"], context["source_document_version"])


async def authenticated(client, session, role="admin"):
    user = User(username="fixture_" + uuid4().hex[:10], password_hash=PASSWORDS.hash(PASSWORD), role=role)
    session.add(user)
    await session.flush()
    raw = "fixture-session-" + uuid4().hex
    expires = datetime.now(UTC) + timedelta(hours=1)
    session.add(LoginSession(user_id=user.id, token_hash=digest(raw), expires_at=expires))
    await session.commit()
    client.cookies.set("schemeguard_session", raw)
    headers = ORIGIN | {"X-CSRF-Token": csrf_token(raw)}
    return Administrator(user.id, user.username, expires, csrf_token(raw)), headers


async def approve(client, headers, scheme_id):
    response = await client.post(
        "/api/v1/admin/sources",
        headers=headers,
        json={
            "scheme_id": str(scheme_id),
            "url": "https://scholarships.gov.in/public/test-fixture.pdf",
            "title": "Synthetic test document",
            "publisher": "Synthetic test publisher",
            "notes": "Isolated deterministic test data; never used in production.",
            "authorized_public_document": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["source_id"]


async def upload(client, headers, source_id, content=None):
    return await client.post(
        "/api/v1/admin/documents",
        params={"source_id": str(source_id), "original_filename": "synthetic.pdf", "attested": "true"},
        headers=headers | {"Content-Type": "application/pdf"},
        content=content if content is not None else pdf_content(),
    )
