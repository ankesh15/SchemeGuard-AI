from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    postgres_user: str = "schemeguard"
    postgres_password: SecretStr | None = None
    postgres_db: str = "schemeguard"
    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    database_url: SecretStr | None = None
    database_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    cors_origins: list[str] = []
    seed_data_path: Path = Path("/app/data/scholarships.json")

    @field_validator("postgres_password")
    @classmethod
    def password_not_empty(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("POSTGRES_PASSWORD must not be empty")
        return value

    @model_validator(mode="after")
    def require_credentials(self) -> "Settings":
        if self.database_url is None and self.postgres_password is None:
            raise ValueError("Set POSTGRES_PASSWORD or DATABASE_URL")
        return self

    @field_validator("cors_origins")
    @classmethod
    def explicit_cors_origins(cls, values: list[str]) -> list[str]:
        from urllib.parse import urlsplit

        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or "*" in value
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins")
        return [value.rstrip("/") for value in values]

    @property
    def sqlalchemy_url(self) -> URL:
        if self.database_url:
            url = make_url(self.database_url.get_secret_value())
            if url.drivername != "postgresql+asyncpg":
                raise ValueError("DATABASE_URL must use postgresql+asyncpg")
            return url
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value() if self.postgres_password else None,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
