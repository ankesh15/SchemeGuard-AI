from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class SourceApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    scheme_id: UUID
    url: str = Field(min_length=8, max_length=2000)
    title: str = Field(min_length=3, max_length=300)
    publisher: str = Field(min_length=3, max_length=200)
    notes: str = Field(min_length=20, max_length=2000)
    authorized_public_document: StrictBool


class SourceApprovalRead(BaseModel):
    source_id: UUID
    scheme_id: UUID
    scheme_name: str
    url: str
    title: str
    publisher: str
    approved_at: datetime
    revoked_at: datetime | None


class RemoteDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: UUID
    published_on: date | None = None


class DocumentRead(BaseModel):
    id: UUID
    scheme_id: UUID
    scheme_name: str
    source_id: UUID
    source_url: str
    original_filename: str
    checksum: str
    content_type: str
    file_size: int
    retrieved_at: datetime
    publication_date: date | None
    version_number: int
    supersedes_id: UUID | None
    storage_key: str
    page_count: int
    processing_status: str
    acquisition_method: str
    pdf_metadata: dict[str, Any]


class DocumentPageResponse(BaseModel):
    items: list[DocumentRead]
    page: int
    page_size: int
    total: int


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_version_id: UUID
    status: str
    provider: str
    model: str | None
    input_chunk_count: int
    candidate_count: int
    schema_version: str
    started_at: datetime
    finished_at: datetime | None


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["parse_only", "gemini"] = "gemini"
