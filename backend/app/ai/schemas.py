"""Flat, bounded structured output mapped into the existing engine AST."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

from app.eligibility.expressions import ValueType

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Scalar = (
    Annotated[str, Field(max_length=200)]
    | StrictBool
    | StrictInt
    | Annotated[StrictFloat, Field(allow_inf_nan=False)]
    | None
)


class CandidateNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Key
    kind: Literal["comparison", "and", "or", "exclude", "if", "unsupported"]
    field: Key | None = None
    operator: Literal["==", "!=", ">", "<", ">=", "<=", "IN", "NOT IN"] | None = None
    expected_value: Scalar | Annotated[list[Scalar], Field(max_length=50)] = None
    value_type: ValueType | None = None
    units: str | None = Field(default=None, max_length=40)
    children: list[Key] = Field(default_factory=list, max_length=32)
    expression: Key | None = None
    when: Key | None = None
    then: Key | None = None
    otherwise: Key | None = None


class CandidateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_key: Key
    source_page: int = Field(ge=1, le=200)
    supporting_excerpt: str = Field(min_length=15, max_length=2000)


class CandidateRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition_identifier: Key
    label: str = Field(min_length=1, max_length=200)
    root: Key | None
    nodes: list[CandidateNode] = Field(max_length=32)
    evidence: list[CandidateReference] = Field(max_length=64)
    extraction_uncertainty: list[Annotated[str, Field(max_length=500)]] = Field(max_length=12)


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_id: UUID
    source_document_version: UUID
    logical_relationship: Literal["and", "or", "unspecified"]
    candidates: list[CandidateRule] = Field(max_length=32)
    limitations: list[Annotated[str, Field(max_length=500)]] = Field(max_length=12)
