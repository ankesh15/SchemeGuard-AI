from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from app.eligibility.engine import Result
from app.eligibility.expressions import ProfileField

InputValue = (
    StrictBool
    | StrictInt
    | Annotated[float, Field(strict=True, allow_inf_nan=False)]
    | Annotated[str, Field(strict=True, max_length=200)]
    | None
)
ProfileKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class EligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_id: UUID
    synthetic_profile: StrictBool
    profile: dict[ProfileKey, InputValue] = Field(max_length=32)

    @field_validator("synthetic_profile")
    @classmethod
    def only_synthetic_profiles(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Phase 2 accepts synthetic development profiles only")
        return value


class EvidenceRead(BaseModel):
    id: UUID
    document_version_id: UUID
    document_sha256: str
    source_title: str
    publisher: str
    locator: str
    excerpt: str
    url: str
    is_demo: bool


class RuleVersionRead(BaseModel):
    id: UUID
    version_number: int
    title: str
    approval_status: Literal["APPROVED"] = "APPROVED"
    approval_basis: str
    approved_at: datetime
    effective_from: date
    effective_to: date | None
    source_document_version_id: UUID
    source_document_sha256: str
    scope_note: str


class RequirementRead(BaseModel):
    key: str
    label: str
    evidence: list[EvidenceRead]


class RequirementsRead(BaseModel):
    scheme_id: UUID
    scheme_name: str
    is_demo: bool
    available: bool
    rule_set: RuleVersionRead | None
    fields: list[ProfileField]
    requirements: list[RequirementRead]
    notices: list[str]
    official_application_url: str | None


class DecisionTrace(BaseModel):
    key: str
    label: str
    kind: str
    result: Result
    explanation: str
    missing_fields: list[str]
    evidence: list[EvidenceRead]
    children: list["DecisionTrace"]


class MissingFieldRead(BaseModel):
    key: str
    label: str


class EligibilityReport(BaseModel):
    scheme_id: UUID
    scheme_name: str
    is_demo: bool
    result: Result
    assessment: str
    reason: Literal["EVALUATED", "NO_APPROVED_RULE_SET"]
    evaluated_at: datetime
    assessed_on: date
    rule_set: RuleVersionRead | None
    requirements: list[DecisionTrace]
    trace: DecisionTrace | None
    missing_fields: list[MissingFieldRead]
    notices: list[str]
    official_application_url: str | None
