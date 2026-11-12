from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.core.enums import Applicability, IndianState, SchemeStatus


class SchemeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    page: int = Field(default=1, ge=1, le=100_000)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_-]*$")
    state: IndianState | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().casefold()
            return next((state for state in IndianState if state.value.casefold() == normalized), value)
        return value


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: HttpUrl
    title: str
    publisher: str
    is_primary: bool
    supported_fields: list[str]
    verification_notes: str
    verified_on: date


class SchemeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_demo: bool = False
    slug: str
    name: str
    description: str | None
    ministry: str | None
    department: str | None
    category: str
    applicability: Applicability
    applicable_states: list[IndianState] | None
    official_source_url: HttpUrl | None
    verified_on: date | None
    status: SchemeStatus
    created_at: datetime
    updated_at: datetime


class SchemeDetail(SchemeRead):
    sources: list[SourceRead]


class SchemePage(BaseModel):
    items: list[SchemeRead]
    total: int
    page: int
    page_size: int
    pages: int


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyRead(BaseModel):
    status: Literal["ready"] = "ready"
    database: Literal["ok"] = "ok"
