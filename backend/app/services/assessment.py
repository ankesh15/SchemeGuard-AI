"""Stateless scheme assessments. No writes to policies, assessments, jobs or notifications."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.assessment.templates import (
    DISCLAIMER,
    ILLUSTRATIVE_NOTICE,
    AssessmentMode,
    DemonstrationTemplate,
    assessment_mode,
    content_hash,
    scoped_program,
    templates,
)
from app.eligibility.engine import Result, Trace, evaluate
from app.eligibility.expressions import Group, ProfileError, Program
from app.models import RuleSet, Scheme
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.assessment import (
    ApplicantDetail,
    AssessmentReport,
    AssessmentRequest,
    AssessmentRequirements,
    TemplateRead,
)
from app.schemas.eligibility import (
    DecisionTrace,
    EvaluationInput,
    InputValue,
    MissingFieldRead,
    RequirementRead,
)
from app.services.eligibility import EligibilityService

logger = logging.getLogger("schemeguard.assessment")
LABELS = {
    Result.PASS: "Criteria matched",
    Result.FAIL: "Criteria not matched",
    Result.UNKNOWN: "Additional information required",
}


@dataclass
class AssessmentContext:
    scheme: Scheme
    rule: RuleSet | None
    program: Program | None
    mode: AssessmentMode
    template: DemonstrationTemplate | None
    notes: dict[str, str]

    @property
    def token(self) -> str:
        return content_hash(
            {
                "scheme_id": str(self.scheme.id),
                "mode": self.mode,
                "rule_id": str(self.rule.id) if self.rule else None,
                "template": self.template.model_dump(mode="json") if self.template else None,
                "program": self.program.model_dump(mode="json") if self.program else None,
            }
        )

    @property
    def template_info(self) -> TemplateRead | None:
        if not self.template:
            return None
        return TemplateRead(
            id=self.template.id,
            version=self.template.version,
            title=self.template.title,
            description=self.template.description,
            content_sha256=self.token,
        )

    @property
    def notices(self) -> list[str]:
        return [DISCLAIMER, *([ILLUSTRATIVE_NOTICE] if self.mode == "ILLUSTRATIVE" else [])]


class AssessmentService:
    def __init__(self, schemes: SchemeRepository, rules: RuleRepository) -> None:
        self.schemes, self.rules = schemes, rules

    async def context(self, scheme_id: UUID, assessed_on: date | None = None) -> AssessmentContext:
        # All policy ambiguity, broken evidence and approval errors propagate. A template
        # must never hide an unsafe/ambiguous approved-policy configuration.
        scheme, rule, program = await EligibilityService(self.schemes, self.rules, assessed_on).load(
            scheme_id
        )
        mode = assessment_mode(scheme, rule is not None)
        template: DemonstrationTemplate | None = None
        notes: dict[str, str] = {}
        if mode == "ILLUSTRATIVE":
            template = templates()[scheme.category]
            program, notes = scoped_program(template, scheme)
        elif mode == "UNSUPPORTED":
            rule, program = None, None
        return AssessmentContext(scheme, rule, program, mode, template, notes)

    @staticmethod
    def sample(context: AssessmentContext) -> dict[str, InputValue]:
        values: dict[str, InputValue] = {}
        if context.template:
            values = dict(context.template.sample_profile)
            if "location_match" in context.notes:
                values["state"] = (context.scheme.applicable_states or [])[0]
            return values
        # Generic questionnaire examples, not inferred government eligibility values.
        for field in context.program.fields if context.program else []:
            if field.choices:
                values[field.key] = field.choices[0].value
            elif field.value_type == "boolean":
                values[field.key] = False
            elif field.value_type == "number":
                value = max(field.minimum or 0, 21)
                if field.maximum is not None:
                    value = min(value, field.maximum)
                values[field.key] = int(value) if field.integer else value
            elif field.value_type == "date":
                values[field.key] = date.today().isoformat()
        return values

    async def requirements(self, scheme_id: UUID) -> AssessmentRequirements:
        context = await self.context(scheme_id)
        scheme, rule, program = context.scheme, context.rule, context.program
        evidence = EligibilityService.evidence(rule, scheme) if rule else {}
        children = program.expression.children if program and isinstance(program.expression, Group) else []
        return AssessmentRequirements(
            scheme_id=scheme.id,
            scheme_name=scheme.name if not scheme.is_demo else "Project learning assessment",
            is_demo=scheme.is_demo,
            available=program is not None,
            rule_set=EligibilityService.version(rule) if rule else None,
            fields=program.fields if program else [],
            requirements=[
                RequirementRead(key=item.key, label=item.label, evidence=evidence.get(item.key, []))
                for item in children
            ],
            notices=context.notices,
            official_application_url=EligibilityService.application_url(scheme),
            category=scheme.category,
            official_source_url=scheme.official_source_url,
            assessment_mode=context.mode,
            template=context.template_info,
            criteria_token=context.token,
            criteria_notes=context.notes,
            sample_profile=self.sample(context),
        )

    async def check(self, request: AssessmentRequest) -> AssessmentReport:
        context = await self.context(request.scheme_id, request.assessed_on)
        scheme, program = context.scheme, context.program
        if request.criteria_token and request.criteria_token != context.token:
            raise HTTPException(
                409, "Assessment criteria changed. Reload the questionnaire before continuing."
            )
        details: list[ApplicantDetail] = []
        if program:
            # Validate against the actual selected questionnaire before exposing any input.
            try:
                evaluated = evaluate(program, request.profile)
            except ProfileError as error:
                raise RequestValidationError(
                    [
                        {
                            "type": "value_error",
                            "loc": ("body", "profile", error.field),
                            "msg": error.message,
                            "input": None,
                        }
                    ]
                ) from error
            details = [
                ApplicantDetail(key=field.key, label=field.label, value=request.profile[field.key])
                for field in program.fields
                if request.profile.get(field.key) is not None
            ]
        elif request.profile:
            raise HTTPException(422, "No assessment is supported here; applicant details are not accepted.")

        if context.mode == "APPROVED_POLICY":
            assert context.rule is not None
            report = await EligibilityService(
                self.schemes,
                self.rules,
                request.assessed_on,
                rule_set_id=context.rule.id,
            ).check(
                EvaluationInput(
                    scheme_id=request.scheme_id, assessed_on=request.assessed_on, profile=request.profile
                )
            )
            return AssessmentReport(
                **report.model_dump(exclude={"notices"}),
                notices=[
                    DISCLAIMER,
                    *[notice for notice in report.notices if notice.startswith("Policy currency warning")],
                ],
                assessment_mode=context.mode,
                category=scheme.category,
                official_source_url=scheme.official_source_url,
                template=None,
                criteria_token=context.token,
                criteria_notes={},
                applicant_details=details,
            )

        def trace(node: Trace) -> DecisionTrace:
            return DecisionTrace(
                **node.model_dump(exclude={"children"}),
                evidence=[],
                children=[trace(child) for child in node.children],
            )

        decision = trace(evaluated) if program else None
        labels = {field.key: field.label for field in program.fields} if program else {}
        result = decision.result if decision else Result.UNKNOWN
        logger.info("illustrative_assessment_evaluated" if decision else "assessment_unsupported")
        return AssessmentReport(
            scheme_id=scheme.id,
            scheme_name=scheme.name if not scheme.is_demo else "Project learning assessment",
            is_demo=scheme.is_demo,
            result=result,
            assessment=LABELS[result],
            reason="EVALUATED" if decision else "NO_APPROVED_RULE_SET",
            evaluated_at=datetime.now(UTC),
            assessed_on=request.assessed_on or datetime.now(ZoneInfo("Asia/Kolkata")).date(),
            rule_set=None,
            requirements=decision.children if decision else [],
            trace=decision,
            missing_fields=[MissingFieldRead(key=key, label=labels[key]) for key in decision.missing_fields]
            if decision
            else [],
            notices=context.notices,
            official_application_url=EligibilityService.application_url(scheme),
            category=scheme.category,
            official_source_url=scheme.official_source_url,
            assessment_mode=context.mode,
            template=context.template_info,
            criteria_token=context.token,
            criteria_notes=context.notes,
            applicant_details=details,
        )
