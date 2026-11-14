"""Read-only, versioned demonstration templates. These are never RuleSet records."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import IndianState
from app.eligibility.engine import Result, evaluate
from app.eligibility.expressions import Choice, Comparison, Group, ProfileField, Program
from app.models import Scheme
from app.schemas.eligibility import InputValue, ProfileKey

type AssessmentMode = Literal["APPROVED_POLICY", "ILLUSTRATIVE", "UNSUPPORTED"]

DISCLAIMER = "SchemeGuard AI is a project demonstration. Results are estimates and do not determine government eligibility."
ILLUSTRATIVE_NOTICE = "These category-based assessment criteria are project-authored illustrations, not verified government requirements."


def content_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class DemonstrationTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,60}$")
    version: int = Field(ge=1)
    basis: Literal["project_authored_illustration"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    categories: list[str] = Field(min_length=1, max_length=12)
    program: Program
    criteria_notes: dict[str, str]
    sample_profile: dict[ProfileKey, InputValue]

    @model_validator(mode="after")
    def valid_reference(self) -> "DemonstrationTemplate":
        if not isinstance(self.program.expression, Group) or self.program.expression.kind != "and":
            raise ValueError("Templates require an explicit AND root")
        if set(self.criteria_notes) != {item.key for item in self.program.expression.children}:
            raise ValueError("Each assessment criterion requires its own project-authored description")
        if evaluate(self.program, self.sample_profile).result != Result.PASS:
            raise ValueError("The sample must be valid and demonstrate matched template criteria")
        return self


@lru_cache(maxsize=1)
def templates() -> dict[str, DemonstrationTemplate]:
    result: dict[str, DemonstrationTemplate] = {}
    identifiers: set[str] = set()
    for file in sorted((Path(__file__).parent / "templates").glob("*.json")):
        template = DemonstrationTemplate.model_validate_json(file.read_text())
        if template.id in identifiers:
            raise ValueError("Duplicate assessment template ID")
        identifiers.add(template.id)
        for category in template.categories:
            if category in result:
                raise ValueError("Multiple assessment templates claim one category")
            result[category] = template
    if not result:
        raise ValueError("No assessment templates were packaged")
    return result


def assessment_mode(scheme: Scheme, approved: bool) -> AssessmentMode:
    if scheme.is_demo or scheme.status == "inactive":
        return "UNSUPPORTED"
    if approved:
        return "APPROVED_POLICY"
    return "ILLUSTRATIVE" if scheme.category in templates() else "UNSUPPORTED"


def scoped_program(template: DemonstrationTemplate, scheme: Scheme) -> tuple[Program, dict[str, str]]:
    """Ask for state only when catalog coverage is verified, and mark it illustrative too."""
    program = template.program.model_copy(deep=True)
    notes = dict(template.criteria_notes)
    if scheme.applicability == "states" and scheme.applicable_states:
        states = [
            state for state in scheme.applicable_states if state in {item.value for item in IndianState}
        ]
        if not states:
            return program, notes
        field = ProfileField(
            key="state",
            label="State or union territory",
            value_type="string",
            section="Your location",
            help_text="Used for the illustrative location match against the catalog's listed areas.",
            choices=[Choice(value=state.value, label=state.value) for state in IndianState],
        )
        assert isinstance(program.expression, Group)
        program = Program(
            fields=[*program.fields, field],
            expression=program.expression.model_copy(
                update={
                    "children": [
                        *program.expression.children,
                        Comparison(
                            kind="comparison",
                            key="location_match",
                            label="Listed location match",
                            field="state",
                            operator="IN",
                            value_type="string",
                            value=[str(state) for state in states],
                        ),
                    ]
                }
            ),
        )
        notes["location_match"] = (
            "For this illustration, your state matches a listed catalog area: "
            + ", ".join(states)
            + ". This is not a verified eligibility rule."
        )
    return program, notes
