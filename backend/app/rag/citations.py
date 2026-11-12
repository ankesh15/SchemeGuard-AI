from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    scheme_id: UUID
    document_version_id: UUID
    document_sha256: str
    chunk_id: UUID | None = None
    page_number: int | None = Field(default=None, ge=1)
    locator: str
    excerpt: str
    source_title: str
    publisher: str
    source_url: str
    url: str
    approved_rule_set_id: UUID


def page_url(url: str, page: int | None) -> str:
    return url.split("#", 1)[0] + f"#page={page}" if page else url
