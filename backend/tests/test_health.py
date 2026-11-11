import json
import logging
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import create_app


async def test_health_and_ready(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    UUID(response.headers["x-request-id"])
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


async def test_database_outage_preserves_health_and_fails_readiness(test_settings):
    settings = Settings(
        database_url=test_settings.sqlalchemy_url.set(host="127.0.0.1", port=1).render_as_string(
            hide_password=False
        ),
        database_timeout_seconds=0.25,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            assert (await client.get("/health")).status_code == 200
            for path in ("/ready", "/api/v1/schemes"):
                response = await client.get(path)
                assert response.status_code == 503
                assert response.json()["error"]["code"] == "database_unavailable"
                assert response.json()["request_id"] == response.headers["x-request-id"]
                assert "password" not in response.text.lower()


async def test_cors_and_read_only_routes(client):
    allowed = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    denied = await client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in denied.headers
    assert (await client.post("/api/v1/schemes", json={})).status_code == 405


def test_json_logging_omits_exception_text():
    try:
        raise ValueError("sensitive-password")
    except ValueError:
        import sys

        record = logging.LogRecord("test", logging.ERROR, "", 0, "failed", (), sys.exc_info())
    output = JsonFormatter().format(record)
    assert json.loads(output)["error_type"] == "ValueError"
    assert "sensitive-password" not in output


async def test_unexpected_errors_are_sanitized(test_settings):
    app = create_app(test_settings)

    @app.get("/test-error")
    async def fail():
        raise RuntimeError("sensitive-error-details")

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.get("/test-error")
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "internal_error"
            assert "sensitive-error-details" not in response.text
            assert response.json()["request_id"] == response.headers["x-request-id"]
