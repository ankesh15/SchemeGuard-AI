from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.demo_policy import POLICY_FILENAME
from app.eligibility.engine import ASSESSMENTS, Result, Trace, evaluate
from app.eligibility.expressions import EXPRESSION_ADAPTER, Group, ProfileError, ProfileField, Program
from app.models import RuleSet, Scheme
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.eligibility import (
    DecisionTrace,
    EligibilityReport,
    EligibilityRequest,
    EvidenceRead,
    MissingFieldRead,
    RequirementRead,
    RequirementsRead,
    RuleVersionRead,
)

NOT_OFFICIAL = "This is an assessment of known conditions, not official government approval, a funding guarantee, or an application submission."


class EligibilityService:
    def __init__(
        self, schemes: SchemeRepository, rules: RuleRepository, assessed_on: date | None = None
    ) -> None:
        self.schemes = schemes
        self.rules = rules
        self.assessed_on = assessed_on or datetime.now(ZoneInfo("Asia/Kolkata")).date()

    async def load(self, scheme_id: UUID) -> tuple[Scheme, RuleSet | None, Program | None]:
        scheme = await self.schemes.get(scheme_id)
        if scheme is None:
            raise HTTPException(404, "Scheme not found")
        rule_set = await self.rules.approved_for(scheme_id, self.assessed_on)
        if rule_set is None or scheme.status == "inactive":
            return scheme, None, None
        if not scheme.is_demo and rule_set.approval_basis != "human_review":
            raise HTTPException(503, "Approved policy requires human review")
        try:
            if not rule_set.conditions or any(not condition.evidence for condition in rule_set.conditions):
                raise ValueError("Incomplete approved rule set")
            children = []
            for condition in rule_set.conditions:
                expression = EXPRESSION_ADAPTER.validate_python(condition.expression)
                if expression.key != condition.condition_key:
                    raise ValueError("Condition key mismatch")
                children.append(expression)
            program = Program(
                fields=[ProfileField.model_validate(field) for field in rule_set.profile_fields],
                expression=Group.model_validate(
                    {
                        "kind": rule_set.logical_operator,
                        "key": "assessment",
                        "label": "Overall assessment",
                        "children": children,
                    }
                ),
            )
        except (ValidationError, ValueError) as error:
            raise HTTPException(
                503, "Approved rule configuration is unavailable for safe evaluation"
            ) from error
        return scheme, rule_set, program

    @staticmethod
    def version(rule_set: RuleSet) -> RuleVersionRead:
        if rule_set.approved_at is None or rule_set.approval_basis is None:
            raise HTTPException(503, "Rule approval metadata is incomplete")
        return RuleVersionRead(
            id=rule_set.id,
            version_number=rule_set.version_number,
            title=rule_set.title,
            approval_basis=rule_set.approval_basis,
            approved_at=rule_set.approved_at,
            effective_from=rule_set.effective_from,
            effective_to=rule_set.effective_to,
            source_document_version_id=rule_set.source_document_version_id,
            source_document_sha256=rule_set.document.content_sha256,
            scope_note=rule_set.scope_note,
        )

    @staticmethod
    def notices(scheme: Scheme, available: bool) -> list[str]:
        notices = [
            NOT_OFFICIAL,
            "Synthetic development profiles only. Applicant inputs and reports are not persisted.",
        ]
        if scheme.is_demo:
            notices.insert(
                0,
                "FICTIONAL DEMO: this is not a government scholarship. All policy values are invented test data.",
            )
        if not available:
            notices.insert(
                0,
                "No approved rule set is effective for this scheme. Government metadata alone is insufficient to assess eligibility.",
            )
        return notices

    @staticmethod
    def application_url(scheme: Scheme) -> str | None:
        # Only the original records have reviewed NSP application provenance.
        # A directory listing is evidence of identity, not an application link.
        nsp_slugs = {
            "aicte-pragati-degree",
            "aicte-saksham-degree",
            "ugc-ishan-uday",
            "pm-yasasvi-top-class-school",
            "pm-usp-csss",
        }
        return (
            "https://scholarships.gov.in/Students"
            if not scheme.is_demo and scheme.slug in nsp_slugs
            else None
        )

    @staticmethod
    def evidence(rule_set: RuleSet, scheme: Scheme) -> dict[str, list[EvidenceRead]]:
        document = rule_set.document
        source = document.source
        return {
            condition.condition_key: [
                EvidenceRead(
                    id=item.id,
                    document_version_id=item.document_version_id,
                    document_sha256=document.content_sha256,
                    source_title=source.title,
                    publisher=source.publisher,
                    locator=item.locator,
                    excerpt=item.excerpt,
                    url=f"/policies/{POLICY_FILENAME}" if scheme.is_demo else source.url,
                    is_demo=scheme.is_demo,
                )
                for item in condition.evidence
            ]
            for condition in rule_set.conditions
        }

    async def requirements(self, scheme_id: UUID) -> RequirementsRead:
        scheme, rule_set, program = await self.load(scheme_id)
        references = self.evidence(rule_set, scheme) if rule_set else {}
        return RequirementsRead(
            scheme_id=scheme.id,
            scheme_name=scheme.name,
            is_demo=scheme.is_demo,
            available=rule_set is not None,
            rule_set=self.version(rule_set) if rule_set else None,
            fields=program.fields if program else [],
            requirements=[
                RequirementRead(
                    key=item.condition_key, label=item.label, evidence=references[item.condition_key]
                )
                for item in rule_set.conditions
            ]
            if rule_set
            else [],
            notices=self.notices(scheme, rule_set is not None),
            official_application_url=self.application_url(scheme),
        )

    async def check(self, request: EligibilityRequest) -> EligibilityReport:
        scheme, rule_set, program = await self.load(request.scheme_id)
        trace: DecisionTrace | None = None
        missing: list[MissingFieldRead] = []
        if rule_set and program:
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
            references = self.evidence(rule_set, scheme)

            def with_evidence(node: Trace, inherited: list[EvidenceRead]) -> DecisionTrace:
                evidence = references.get(node.key, inherited)
                return DecisionTrace(
                    **node.model_dump(exclude={"children"}),
                    evidence=evidence,
                    children=[with_evidence(child, evidence) for child in node.children],
                )

            trace = with_evidence(evaluated, [])
            labels = {field.key: field.label for field in program.fields}
            missing = [MissingFieldRead(key=key, label=labels[key]) for key in trace.missing_fields]
        result = trace.result if trace else Result.UNKNOWN
        return EligibilityReport(
            scheme_id=scheme.id,
            scheme_name=scheme.name,
            is_demo=scheme.is_demo,
            result=result,
            assessment=ASSESSMENTS[result],
            reason="EVALUATED" if trace else "NO_APPROVED_RULE_SET",
            evaluated_at=datetime.now(UTC),
            assessed_on=self.assessed_on,
            rule_set=self.version(rule_set) if rule_set else None,
            requirements=trace.children if trace else [],
            trace=trace,
            missing_fields=missing,
            notices=self.notices(scheme, trace is not None),
            official_application_url=self.application_url(scheme),
        )
