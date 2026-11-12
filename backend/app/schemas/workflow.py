from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool

from app.eligibility.expressions import ProfileField

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")]


class EvidenceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    node_key: Key
    page_number: int = Field(ge=1, le=200)
    excerpt: str = Field(min_length=15, max_length=2000)


class ProposedCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: Key
    label: str = Field(min_length=1, max_length=200)
    source_candidate_id: UUID | None = None
    expression: dict[str, JsonValue] | None
    evidence: list[EvidenceAnchor] = Field(default_factory=list, max_length=32)


class ExcludedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: UUID
    reason: str = Field(min_length=20, max_length=1000)


class PolicyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=200)
    logical_operator: Literal["and", "or"] = "and"
    effective_from: date | None = None
    effective_to: date | None = None
    effective_date_basis: Literal["unverified", "official_stated", "reviewer_activation"] = "unverified"
    effective_date_note: str = Field(default="", max_length=2000)
    effective_date_evidence: EvidenceAnchor | None = None
    scope_note: str = Field(default="", max_length=4000)
    applicability_note: str = Field(default="", max_length=4000)
    profile_fields: list[ProfileField] = Field(default_factory=list, max_length=32)
    field_units: dict[str, Annotated[str, Field(max_length=40)]] = Field(default_factory=dict, max_length=32)
    conditions: list[ProposedCondition] = Field(default_factory=list, max_length=32)
    excluded_candidates: list[ExcludedCandidate] = Field(default_factory=list, max_length=128)
    replaces_rule_set_ids: list[UUID] = Field(default_factory=list, max_length=64)
    replacement_notes: str = Field(default="", max_length=2000)


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_version_id: UUID
    extraction_job_id: UUID | None = None
    request_key: UUID


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    draft: PolicyDraft
    notes: str = Field(min_length=20, max_length=4000)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    proposal_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    notes: str = Field(min_length=20, max_length=4000)
    human_review_confirmed: StrictBool
    complete_policy_confirmed: StrictBool
    applicability_confirmed: StrictBool
    reviewed_pages: list[int] = Field(min_length=1, max_length=200)
    acknowledged_findings: list[str] = Field(default_factory=list, max_length=512)


class RejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    notes: str = Field(min_length=20, max_length=4000)


class CancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    notes: str = Field(min_length=20, max_length=2000)


class DraftValidation(BaseModel):
    publishable: bool
    errors: list[str]
    warnings: list[str]
    overlapping_rule_sets: list[dict[str, JsonValue]]
