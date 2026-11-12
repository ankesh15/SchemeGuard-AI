from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.core.enums import Applicability, IndianState, SchemeStatus


class SourceSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    is_primary: bool
    supported_fields: list[str] = Field(min_length=1)
    verification_notes: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def official_https_source(cls, value: HttpUrl) -> HttpUrl:
        host = value.host or ""
        official = host.endswith((".gov.in", ".nic.in")) or host in {"aicte-india.org", "www.aicte-india.org"}
        if value.scheme != "https" or not official or value.username or value.password or value.port != 443:
            raise ValueError("Seed sources require an official government HTTPS URL")
        return value


class SchemeSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    slug: str = Field(max_length=150, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    ministry: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    category: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", max_length=60)
    applicability: Applicability
    applicable_states: list[IndianState] | None
    verified_on: date
    status: SchemeStatus
    sources: list[SourceSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_evidence(self) -> "SchemeSeed":
        if sum(source.is_primary for source in self.sources) != 1:
            raise ValueError("Exactly one primary source is required")
        if len({str(source.url) for source in self.sources}) != len(self.sources):
            raise ValueError("Duplicate source URL")
        if self.applicability == Applicability.UNKNOWN and self.applicable_states is not None:
            raise ValueError("Unknown applicability must have null states")
        if self.applicability == Applicability.NATIONAL and self.applicable_states != []:
            raise ValueError("National applicability must have an empty state list")
        if self.applicability == Applicability.STATES and not self.applicable_states:
            raise ValueError("State applicability requires verified states")
        supported = {field for source in self.sources for field in source.supported_fields}
        required = {"name", "status"}
        required.update(
            field for field in ("description", "ministry", "department") if getattr(self, field) is not None
        )
        if self.applicability != Applicability.UNKNOWN:
            required.add("applicability")
        if not required.issubset(supported):
            raise ValueError("Every populated factual field must have supporting evidence")
        return self


class SeedManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    review_method: str = Field(min_length=1)
    # Optional for the legacy Phase 1 file; category files declare and validate it.
    category: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]*$", max_length=60)
    schemes: list[SchemeSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_schemes(self) -> "SeedManifest":
        if len({scheme.slug for scheme in self.schemes}) != len(self.schemes):
            raise ValueError("Scheme slugs must be unique")
        if self.category is not None and any(scheme.category != self.category for scheme in self.schemes):
            raise ValueError("Every scheme must match the declared file category")
        return self
