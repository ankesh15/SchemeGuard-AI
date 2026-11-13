import hashlib
import io
import logging
from unittest.mock import Mock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from sqlalchemy import update

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.ingestion.storage import S3DocumentStorage, document_storage
from app.ingestion.validation import IngestionError
from app.models import User
from tests.ingestion_support import ORIGIN, PASSWORD
from tests.test_citizen import citizen_context as citizen_context
from tests.test_citizen import signup


def production(test_settings, **updates):
    values = test_settings.model_dump() | {
        "app_env": "production",
        "profile_encryption_key": SecretStr(Fernet.generate_key().decode()),
        "allow_local_document_storage": True,
        "admin_allowed_origins": ["https://schemes.example.org"],
        "seed_demo_data": False,
    }
    return Settings.model_validate(values | updates)


def test_production_configuration_and_managed_tls(test_settings):
    valid = production(test_settings)
    assert valid.app_env == "production"
    for updates in [
        {"profile_encryption_key": None},
        {"seed_demo_data": True},
        {"allowed_hosts": ["*"]},
        {"admin_allowed_origins": ["http://unsafe.example"]},
        {"allow_local_document_storage": False},
        {"document_storage_backend": "s3", "s3_bucket": None},
        {"s3_endpoint_url": "http://internal.local"},
    ]:
        with pytest.raises(ValidationError):
            production(test_settings, **updates)
    url = test_settings.sqlalchemy_url.update_query_dict({"ssl": "verify-full"})
    configured = production(test_settings, database_url=SecretStr(url.render_as_string(hide_password=False)))
    assert "sslmode=verify-full" in configured.psycopg_dsn


async def test_host_and_global_body_limits(client):
    assert (await client.get("/health", headers={"Host": "attacker.example"})).status_code == 400
    response = await client.post(
        "/api/v1/eligibility/check", headers={"Content-Type": "application/json"}, content=b" " * 16001
    )
    assert response.status_code == 413
    assert (await client.get("/api/v1/schemes?page=9999999999999999999")).status_code == 422


def test_logs_hide_external_secrets_and_include_job_context():
    record = logging.LogRecord("httpx", logging.WARNING, "", 1, "URL https://host/?key=do-not-log", (), None)
    assert "do-not-log" not in JsonFormatter().format(record)
    record = logging.LogRecord("schemeguard.worker", logging.WARNING, "", 1, "durable_job_failed", (), None)
    record.job_id = "synthetic-job"
    record.attempt = 2
    assert '"attempt": 2' in JsonFormatter().format(record)


def test_s3_content_addressing_checksums_and_duplicate_write(test_settings, monkeypatch):
    from botocore.exceptions import ClientError

    settings = test_settings.model_copy(
        update={"document_storage_backend": "s3", "s3_bucket": "synthetic-test-bucket"}
    )
    store = document_storage(settings)
    assert isinstance(store, S3DocumentStorage)
    client = Mock()
    store.__dict__["client"] = client
    data = b"synthetic PDF bytes"
    checksum = hashlib.sha256(data).hexdigest()
    key, sha = store.put(uuid4(), data)
    assert sha == checksum and key.endswith(checksum + ".pdf")
    assert client.put_object.call_args.kwargs["IfNoneMatch"] == "*"
    assert client.put_object.call_args.kwargs["ServerSideEncryption"] == "AES256"
    client.get_object.return_value = {"ContentLength": len(data), "Body": io.BytesIO(data)}
    assert store.read(key, checksum, 100) == data
    client.put_object.side_effect = ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
    client.get_object.return_value = {"ContentLength": len(data), "Body": io.BytesIO(data)}
    store.put(uuid4(), data)
    client.get_object.return_value = {"ContentLength": 4, "Body": io.BytesIO(b"fake")}
    with pytest.raises(IngestionError, match="checksum"):
        store.read(key, checksum, 100)
    with pytest.raises(IngestionError):
        store.read("../private", checksum, 100)


async def test_password_change_cannot_race_in_flight_login(client, session, citizen_context, monkeypatch):
    data, _ = await signup(client)
    user = await session.get(User, data["user_id"])
    from app.auth.security import PASSWORDS

    original_hash = user.password_hash

    # Change the stored hash between successful old-password verification and session creation.
    async def verification(*args, **kwargs):
        if args[0].__name__ == "verify_password":
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(password_hash=PASSWORDS.hash("Changed-synthetic-password-123!"))
            )
            await session.commit()
            return True
        return args[0](*args[1:], **kwargs)

    monkeypatch.setattr("app.api.v1.admin_auth.asyncio.to_thread", verification)
    response = await client.post(
        "/api/v1/auth/login", headers=ORIGIN, json={"username": data["username"], "password": PASSWORD}
    )
    assert response.status_code == 401, response.text
    await session.refresh(user)
    assert original_hash != user.password_hash
