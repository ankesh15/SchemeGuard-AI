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
    seed_data_path: Path = Path("/app/data/schemes")
    seed_demo_data: bool = False
    document_storage_root: Path = Path("/var/lib/schemeguard/documents")
    pdf_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    pdf_max_pages: int = Field(default=50, ge=1, le=200)
    pdf_parse_timeout: float = Field(default=25, ge=1, le=60)
    pdf_max_text_chars: int = Field(default=200_000, ge=1000, le=1_000_000)
    document_download_timeout: float = Field(default=15, ge=1, le=30)
    chunk_size: int = Field(default=1800, ge=200, le=6000)
    chunk_overlap: int = Field(default=160, ge=0, le=1000)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(
        default="gemini-3.6-flash", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$"
    )
    gemini_timeout: float = Field(default=20, ge=1, le=60)
    gemini_max_retries: int = Field(default=2, ge=0, le=4)
    gemini_max_requests: int = Field(default=6, ge=1, le=12)
    gemini_max_input_chars: int = Field(default=20_000, ge=1000, le=50_000)
    processing_timeout: float = Field(default=90, ge=10, le=300)
    admin_allowed_origins: list[str] = ["http://localhost:3000"]
    admin_session_hours: int = Field(default=8, ge=1, le=24)
    admin_login_limit: int = Field(default=10, ge=3, le=30)
    admin_rate_window_seconds: int = Field(default=900, ge=60, le=3600)
    profile_encryption_key: SecretStr | None = None
    citizen_session_hours: int = Field(default=8, ge=1, le=24)
    redis_url: str = "redis://redis:6379/0"
    worker_job_attempts: int = Field(default=4, ge=1, le=8)
    worker_lease_seconds: int = Field(default=600, ge=60, le=1800)
    monitoring_dispatch_seconds: int = Field(default=30, ge=10, le=300)
    workflow_timeout: float = Field(default=150, ge=15, le=300)
    workflow_max_attempts: int = Field(default=3, ge=1, le=5)
    embedding_provider: Literal["gemini", "local_hash"] = "gemini"
    embedding_model: str = Field(default="gemini-embedding-001", pattern=r"^[a-zA-Z0-9._-]+$", max_length=100)
    embedding_dimensions: int = Field(default=768, ge=768, le=768)
    embedding_timeout: float = Field(default=20, ge=1, le=60)
    embedding_max_retries: int = Field(default=2, ge=0, le=3)
    rag_top_k: int = Field(default=5, ge=1, le=10)
    rag_max_chunks: int = Field(default=500, ge=1, le=1000)
    rag_min_similarity: float = Field(default=0.3, ge=0, le=1)
    explanation_use_gemini: bool = False

    @model_validator(mode="after")
    def ingestion_limits(self) -> "Settings":
        if self.profile_encryption_key:
            from cryptography.fernet import Fernet

            try:
                Fernet(self.profile_encryption_key.get_secret_value().encode())
            except (ValueError, TypeError) as error:
                raise ValueError("PROFILE_ENCRYPTION_KEY must be a valid Fernet key") from error
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.app_env == "production" and self.embedding_provider == "local_hash":
            raise ValueError("The local_hash fixture provider is forbidden in production")
        if self.app_env == "production" and any(
            not origin.startswith("https://") for origin in self.admin_allowed_origins
        ):
            raise ValueError("Production admin origins must use HTTPS")
        return self

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

    @field_validator("cors_origins", "admin_allowed_origins")
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
