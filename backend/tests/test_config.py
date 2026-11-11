import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_password_with_reserved_characters_round_trips():
    settings = Settings(database_url=None, postgres_password="test-only-@:/%#$-value", _env_file=None)
    assert settings.sqlalchemy_url.password == "test-only-@:/%#$-value"
    assert "test-only" not in str(settings.sqlalchemy_url)


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "file:///tmp",
        "https://example.com/path",
        "https://user:password@example.com",
    ],
)
def test_wildcard_and_invalid_cors_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(cors_origins=[origin])


def test_sqlite_is_not_a_supported_backend():
    settings = Settings(database_url="sqlite+aiosqlite:///test.db")
    with pytest.raises(ValueError, match="postgresql"):
        _ = settings.sqlalchemy_url
