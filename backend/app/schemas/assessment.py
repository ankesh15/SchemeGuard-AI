from typing import Literal

from pydantic import BaseModel, Field

from app.assessment.templates import AssessmentMode
from app.schemas.eligibility import EligibilityReport, EvaluationInput, InputValue, RequirementsRead


class AssessmentRequest(EvaluationInput):
    criteria_token: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class TemplateRead(BaseModel):
    id: str
    version: int
    title: str
    description: str
    basis: Literal["project_authored_illustration"] = "project_authored_illustration"
    content_sha256: str


class ApplicantDetail(BaseModel):
    key: str
    label: str
    value: InputValue


class AssessmentRequirements(RequirementsRead):
    assessment_mode: AssessmentMode
    category: str
    official_source_url: str | None
    template: TemplateRead | None
    criteria_token: str
    criteria_notes: dict[str, str]
    sample_profile: dict[str, InputValue]


class AssessmentReport(EligibilityReport):
    assessment_mode: AssessmentMode
    category: str
    official_source_url: str | None
    template: TemplateRead | None
    criteria_token: str
    criteria_notes: dict[str, str]
    applicant_details: list[ApplicantDetail]
