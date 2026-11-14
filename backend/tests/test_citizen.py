"""Synthetic citizen data in a disposable PostgreSQL database."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from app.auth.encryption import seal, unseal
from app.demo_policy import SYNTHETIC_PASS_PROFILE
from app.models import Assessment, CitizenProfile, LoginSession, Notification, ReassessmentEvent, Scheme, User
from tests.ingestion_support import ORIGIN, PASSWORD
from tests.test_eligibility_api import demo_rules as demo_rules


@pytest.fixture
async def citizen_context(client):
    app = client._transport.app
    app.state.settings = app.state.settings.model_copy(
        update={"profile_encryption_key": SecretStr(Fernet.generate_key().decode())}
    )
    return app


async def signup(client, username=None):
    response = await client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"username": username or "citizen_" + uuid4().hex[:12], "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json(), ORIGIN | {"X-CSRF-Token": response.json()["csrf_token"]}


async def test_registration_shared_auth_and_role_protection(client, session, citizen_context):
    data, headers = await signup(client)
    user = await session.get(User, UUID(data["user_id"]))
    assert user.role == data["role"] == "citizen" and user.password_hash.startswith("$argon2")
    assert PASSWORD not in user.password_hash
    assert (await client.get("/api/v1/me")).json()["username"] == user.username
    assert (await client.get("/api/v1/admin/documents")).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/auth/login", headers=ORIGIN, json={"username": user.username, "password": PASSWORD}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"username": "badrole", "password": PASSWORD, "role": "admin"},
        )
    ).status_code == 422
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 204 and (await client.get("/api/v1/me")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", headers=ORIGIN, json={"username": user.username, "password": "invalid"}
        )
    ).status_code == 401
    response = await client.post(
        "/api/v1/auth/login", headers=ORIGIN, json={"username": user.username, "password": PASSWORD}
    )
    assert (
        response.status_code == 200
        and "HttpOnly" in response.headers["set-cookie"]
        and "SameSite=strict" in response.headers["set-cookie"]
    )
    assert (await client.get("/api/v1/me")).headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "a", "password": PASSWORD},
        {"username": "validname", "password": "short"},
        {"username": "validname", "password": PASSWORD, "role": "admin"},
    ],
)
async def test_registration_validation(client, citizen_context, payload):
    assert (await client.post("/api/v1/auth/register", headers=ORIGIN, json=payload)).status_code == 422


async def test_csrf_expiry_password_change_and_sessions(client, session, citizen_context):
    data, headers = await signup(client)
    assert (await client.put("/api/v1/profiles/me", headers=ORIGIN, json={})).status_code == 403
    assert (
        await client.put("/api/v1/profiles/me", headers=headers | {"Origin": "https://evil.example"}, json={})
    ).status_code == 403
    async with AsyncClient(transport=ASGITransport(app=citizen_context), base_url="http://test") as other:
        second = await other.post(
            "/api/v1/auth/login", headers=ORIGIN, json={"username": data["username"], "password": PASSWORD}
        )
        assert second.status_code == 200
        changed = await client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": "Changed-synthetic-password-123!"},
        )
        assert changed.status_code == 204
        assert (await other.get("/api/v1/me")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", headers=ORIGIN, json={"username": data["username"], "password": PASSWORD}
        )
    ).status_code == 401
    logged = await client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"username": data["username"], "password": "Changed-synthetic-password-123!"},
    )
    assert logged.status_code == 200
    await session.execute(
        update(LoginSession)
        .where(LoginSession.user_id == UUID(data["user_id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_profile_encryption_validation_and_delete(client, session, citizen_context):
    data, headers = await signup(client)
    assert not (await client.get("/api/v1/profiles/me")).json()["exists"]
    body = {
        "state": "Assam",
        "age_years": 22,
        "annual_family_income_inr": 123456,
        "current_student": True,
        "attributes": {"study_mode": "full_time"},
    }
    saved = await client.put("/api/v1/profiles/me", headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["completeness"]["percent"] == 80
    row = await session.get(CitizenProfile, UUID(data["user_id"]))
    assert "123456" not in row.encrypted_data and "Assam" not in row.encrypted_data
    assert (
        unseal(citizen_context.state.settings, row.user_id, "profile", row.encrypted_data)["age_years"] == 22
    )
    for bad in [
        {"age_years": True},
        {"age_years": 131},
        {"attributes": {"aadhaar": "123456789012"}},
        {"annual_family_income_inr": -1},
        {"attributes": {"age_years": 30}},
        {"attributes": {"enrollment_date": "not-a-date"}},
    ]:
        assert (await client.put("/api/v1/profiles/me", headers=headers, json=bad)).status_code == 422
    assert (await client.get("/api/v1/profiles/options")).status_code == 200
    assert (await client.delete("/api/v1/profiles/me", headers=headers)).status_code == 204
    assert not (await client.get("/api/v1/profiles/me")).json()["exists"]


async def test_encryption_binding_and_missing_config(client, citizen_context):
    from fastapi import HTTPException

    settings = citizen_context.state.settings
    owner = uuid4()
    encrypted = seal(settings, owner, "profile", {"age": 20})
    for user, purpose in [(uuid4(), "profile"), (owner, "other")]:
        with pytest.raises(HTTPException):
            unseal(settings, user, purpose, encrypted)
    citizen_context.state.settings = settings.model_copy(update={"profile_encryption_key": None})
    assert (
        await client.post(
            "/api/v1/auth/register", headers=ORIGIN, json={"username": "unconfigured", "password": PASSWORD}
        )
    ).status_code == 503


async def test_saved_assessments_isolation_idempotence_and_reproduction(
    client, session, citizen_context, demo_rules
):
    data, headers = await signup(client)
    payload = {
        "scheme_id": str(demo_rules),
        "request_key": str(uuid4()),
        "use_saved_profile": False,
        "profile": SYNTHETIC_PASS_PROFILE,
    }
    response = await client.post("/api/v1/assessments", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["result"] == "PASS" and saved["rule_version"] == 1
    again = await client.post("/api/v1/assessments", headers=headers, json=payload)
    assert again.json()["id"] == saved["id"]
    assert (
        await client.post("/api/v1/assessments", headers=headers, json=payload | {"profile": {}})
    ).status_code == 409
    assert (await client.post(f"/api/v1/assessments/{saved['id']}/reproduce", headers=headers)).json()[
        "matches_original"
    ]
    item = await session.get(Assessment, UUID(saved["id"]))
    assert "annual_income_inr" not in item.encrypted_snapshot
    async with AsyncClient(transport=ASGITransport(app=citizen_context), base_url="http://test") as other:
        _, other_headers = await signup(other)
        assert (await other.get(f"/api/v1/assessments/{saved['id']}")).status_code == 404
        assert (
            await other.post(f"/api/v1/assessments/{saved['id']}/reproduce", headers=other_headers)
        ).status_code == 404
        assert (await other.get("/api/v1/assessments")).json()["total"] == 0
        assert not (await other.get("/api/v1/profiles/me")).json()["exists"]
    assert (await client.get("/api/v1/assessments?page=0")).status_code == 422
    assert (await client.get("/api/v1/dashboard")).json()["assessment_count"] == 1
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(update(Assessment).where(Assessment.id == item.id).values(result="FAIL"))
    assert (await client.get(f"/api/v1/assessments/{saved['id']}")).json()["result"] == "PASS"


async def test_metadata_only_saved_unknown_and_minimal_snapshot(client, session, citizen_context):
    _, headers = await signup(client)
    scheme = await session.scalar(select(Scheme).limit(1))
    response = await client.post(
        "/api/v1/assessments",
        headers=headers,
        json={"scheme_id": str(scheme.id), "request_key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    assert response.json()["result"] == "UNKNOWN" and response.json()["rule_set_id"] is None
    item = await session.get(Assessment, UUID(response.json()["id"]))
    assert (
        unseal(
            citizen_context.state.settings,
            item.user_id,
            f"assessment-input:{item.id}",
            item.encrypted_snapshot,
        )
        == {}
    )
    assert (await client.post(f"/api/v1/assessments/{item.id}/reproduce", headers=headers)).json()[
        "matches_original"
    ]


async def test_account_deletion_and_preferences(client, session, citizen_context, demo_rules):
    data, headers = await signup(client)
    assert (
        await client.put("/api/v1/profiles/me", headers=headers, json={"age_years": 20})
    ).status_code == 200
    payload = {"scheme_id": str(demo_rules), "request_key": str(uuid4())}
    assert (await client.post("/api/v1/assessments", headers=headers, json=payload)).status_code == 201
    prefs = {"in_app": False, "automatic_reassessment": False, "policy_updates": False}
    assert (await client.put("/api/v1/notification-preferences", headers=headers, json=prefs)).json() == prefs
    assert (await client.get("/api/v1/notification-preferences")).json() == prefs
    assert (
        await client.patch(
            "/api/v1/me", headers=headers, json={"username": "renamed_citizen", "current_password": PASSWORD}
        )
    ).status_code == 200
    assert (
        await client.request(
            "DELETE",
            "/api/v1/me",
            headers=headers,
            json={"current_password": PASSWORD, "acknowledge_deletion": False},
        )
    ).status_code == 422
    response = await client.request(
        "DELETE",
        "/api/v1/me",
        headers=headers,
        json={"current_password": PASSWORD, "acknowledge_deletion": True},
    )
    assert response.status_code == 204, response.text
    assert (await client.get("/api/v1/me")).status_code == 401
    user = await session.get(User, UUID(data["user_id"]), populate_existing=True)
    assert not user.is_active and user.username.startswith("deleted_") and user.password_hash == "disabled"
    for model in (Assessment, CitizenProfile, Notification, ReassessmentEvent):
        assert not await session.scalar(
            select(func.count()).select_from(model).where(model.user_id == user.id)
        )
    assert await session.scalar(select(func.count()).select_from(Scheme)) == 6


@pytest.mark.parametrize(
    "path",
    ["/me", "/profiles/me", "/assessments", "/notifications", "/notification-preferences", "/dashboard"],
)
async def test_private_endpoints_require_session(client, path):
    assert (await client.get("/api/v1" + path)).status_code == 401


async def test_duplicate_user_and_registration_rate_limit(client, citizen_context):
    data, _ = await signup(client)
    body = {"username": data["username"], "password": PASSWORD}
    assert (await client.post("/api/v1/auth/register", headers=ORIGIN, json=body)).status_code == 409
    # Registration and login share the original database-backed limiter infrastructure.
    for _ in range(3):
        assert (await client.post("/api/v1/auth/register", headers=ORIGIN, json=body)).status_code == 409
    assert (await client.post("/api/v1/auth/register", headers=ORIGIN, json=body)).status_code == 429


async def test_private_request_size_and_input_vocabulary(client, citizen_context):
    _, headers = await signup(client)
    response = await client.put(
        "/api/v1/profiles/me", headers=headers | {"Content-Type": "application/json"}, content=b" " * 16001
    )
    assert response.status_code == 413
    assert (
        await client.post(
            "/api/v1/assessments",
            headers=headers,
            json={"scheme_id": str(uuid4()), "request_key": str(uuid4()), "profile": {"aadhaar": "123456"}},
        )
    ).status_code == 422


async def test_dashboard_discovery_uses_profile_relevance_and_verified_geography(client, citizen_context):
    _, headers = await signup(client)
    await client.put(
        "/api/v1/profiles/me",
        headers=headers,
        json={"state": "Assam", "age_years": 25, "interests": ["education"]},
    )
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (
        body["relevant_schemes"] and "not government eligibility determinations" in body["discovery_notice"]
    )
    for scheme in body["relevant_schemes"]:
        if scheme["applicability"] == "states":
            assert "Assam" in scheme["applicable_states"]
        elif scheme["applicability"] == "unknown":
            assert any("coverage has not been verified" in note for note in scheme["missing_information"])
        assert scheme["matching_reasons"]
