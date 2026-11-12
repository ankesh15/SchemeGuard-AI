"""Reusable proposal assembly/validation independent of LangGraph execution."""

import hashlib
import json
from typing import Any
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation import ensure_satisfiable
from app.agents.verification_agent import date_located, finding, located, verify_condition, walk
from app.ai.validation import FIELDS
from app.eligibility.expressions import EXPRESSION_ADAPTER, Comparison, Group, ProfileField, Program
from app.ingestion.pdf_parser import ParsedPage
from app.models import DocumentAsset, DocumentPage, RuleCandidate, RuleSet
from app.schemas.workflow import DraftValidation, EvidenceAnchor, PolicyDraft, ProposedCondition


def proposal_digest(proposal: PolicyDraft) -> str:
    return hashlib.sha256(
        json.dumps(proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prefix_expression(expression: dict[str, Any], prefix: str) -> dict[str, Any]:
    parsed = EXPRESSION_ADAPTER.validate_python(expression)
    result = parsed.model_dump(mode="json")
    result["key"] = (prefix + parsed.key)[:80]
    if parsed.kind in {"and", "or"}:
        result["children"] = [prefix_expression(child, prefix) for child in result["children"]]
    elif parsed.kind == "exclude":
        result["expression"] = prefix_expression(result["expression"], prefix)
    elif parsed.kind == "if":
        for name in ("when", "then", "otherwise"):
            if result.get(name):
                result[name] = prefix_expression(result[name], prefix)
    return result


async def source_pages(session: AsyncSession, document_id: UUID) -> dict[int, ParsedPage]:
    pages = await session.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    return {
        page.page_number: ParsedPage(
            page_number=page.page_number,
            text_content=page.text_content,
            blocks=page.blocks,
            issues=page.issues,
        )
        for page in pages
    }


async def assemble_proposal(
    session: AsyncSession, job_id: UUID, title: str
) -> tuple[PolicyDraft, list[dict[str, Any]]]:
    from app.models import CandidateEvidence, DocumentPage, ProcessingJob

    job = await session.get(ProcessingJob, job_id)
    if job is None:
        raise ValueError("Extraction job not found")
    candidates = list(
        await session.scalars(
            select(RuleCandidate)
            .where(RuleCandidate.job_id == job_id)
            .order_by(RuleCandidate.created_at, RuleCandidate.id)
        )
    )
    if not candidates or len(candidates) > 32:
        raise ValueError("Review requires 1–32 candidate conditions; split larger proposals explicitly")
    conditions, fields, units, findings = [], {}, {}, []
    for index, candidate in enumerate(candidates):
        prefix = f"c{index}_"
        expression = (
            prefix_expression(candidate.mapped_expression, prefix) if candidate.mapped_expression else None
        )
        key = expression["key"] if expression else prefix + candidate.condition_identifier[:60]
        references = await session.execute(
            select(CandidateEvidence, DocumentPage.page_number)
            .join(DocumentPage, DocumentPage.id == CandidateEvidence.page_id)
            .where(CandidateEvidence.candidate_id == candidate.id)
        )
        anchors = [
            EvidenceAnchor(node_key=(prefix + item.node_key)[:80], page_number=number, excerpt=item.excerpt)
            for item, number in references
        ]
        conditions.append(
            ProposedCondition(
                key=key,
                label=candidate.label,
                source_candidate_id=candidate.id,
                expression=expression,
                evidence=anchors,
            )
        )
        if expression:
            for node in walk(EXPRESSION_ADAPTER.validate_python(expression)):
                if isinstance(node, Comparison) and node.field in FIELDS:
                    label, value_type, unit = FIELDS[node.field]
                    fields[node.field] = ProfileField(
                        key=node.field,
                        label=label,
                        value_type=value_type,
                        section="Reviewed policy",
                        help_text=f"Use {unit}." if unit else "",
                    )
                    if unit:
                        units[node.field] = unit
        for message in candidate.validation_issues + candidate.payload.get("extraction_uncertainty", []):
            findings.append(finding(str(candidate.id), "extraction_review", str(message), "warning"))
        if candidate.validation_status in {"INVALID", "CONFLICT"}:
            findings.append(
                finding(
                    str(candidate.id),
                    "invalid_candidate",
                    "The original candidate is invalid/conflicting. Correct or explicitly exclude it before publication.",
                )
            )
    draft = PolicyDraft(
        title=title[:200],
        profile_fields=list(fields.values()),
        field_units=units,
        conditions=conditions,
        scope_note="Unverified proposal. Review all conditions, exclusions, dependencies and policy applicability before publication.",
    )
    pages = await source_pages(session, job.document_version_id)
    for condition in conditions:
        if condition.expression:
            findings += verify_condition(
                condition, EXPRESSION_ADAPTER.validate_python(condition.expression), pages, units
            )
    findings.append(
        finding(
            "policy",
            "complete_policy_review",
            "Extraction does not prove policy completeness or current applicability. Review every source page.",
            "warning",
        )
    )
    return draft, findings


async def validate_draft(
    session: AsyncSession, draft: PolicyDraft, document_id: UUID, scheme_id: UUID, candidate_ids: set[UUID]
) -> tuple[DraftValidation, Program | None, list[dict[str, Any]]]:
    errors, warnings, findings = [], [], []
    pages = await source_pages(session, document_id)
    asset = await session.get(DocumentAsset, document_id)
    if not asset or asset.processing_status != "PARSED" or len(pages) != asset.page_count:
        errors.append(
            "Complete parsed source pages are required; incomplete or missing text cannot be published."
        )
    included = [
        condition.source_candidate_id for condition in draft.conditions if condition.source_candidate_id
    ]
    excluded = [item.candidate_id for item in draft.excluded_candidates]
    if len(set(included + excluded)) != len(included + excluded) or set(included + excluded) != candidate_ids:
        errors.append(
            "Every original candidate must be included exactly once or excluded with a recorded reason."
        )
    if not draft.effective_from or draft.effective_date_basis == "unverified":
        errors.append("An explicitly reviewed activation/effective date and its basis are required.")
    if (
        len(draft.effective_date_note.strip()) < 20
        or len(draft.applicability_note.strip()) < 20
        or len(draft.scope_note.strip()) < 20
    ):
        errors.append("Record detailed effective-date, applicability and scope notes.")
    if draft.effective_to and draft.effective_from and draft.effective_to < draft.effective_from:
        errors.append("The policy end date precedes its start date.")
    if draft.effective_date_basis == "official_stated" and (
        not draft.effective_date_evidence
        or not located(draft.effective_date_evidence, pages)
        or not draft.effective_from
        or not date_located(draft.effective_from, draft.effective_date_evidence.excerpt)
    ):
        errors.append(
            "An official effective-date claim requires located evidence containing that explicit date."
        )
    program = None
    try:
        if not draft.conditions:
            raise ValueError("A complete policy requires at least one condition")
        for field in draft.profile_fields:
            if field.key not in FIELDS or FIELDS[field.key][1] != field.value_type:
                raise ValueError("Profile field is outside the supported typed field vocabulary")
        expressions = []
        for condition in draft.conditions:
            expression = EXPRESSION_ADAPTER.validate_python(condition.expression)
            if expression.key != condition.key:
                raise ValueError("A condition key must equal its expression root key")
            expressions.append(expression)
            findings += verify_condition(condition, expression, pages, draft.field_units)
        program = Program(
            fields=draft.profile_fields,
            expression=Group(
                kind=draft.logical_operator,
                key="assessment",
                label="Overall assessment",
                children=expressions,
            ),
        )
        ensure_satisfiable(program)
    except ValueError as error:
        errors.append(
            "Invalid or contradictory complete rule program: "
            + (
                str(error)[:200]
                if not hasattr(error, "errors")
                else "typed expression/profile validation failed"
            )
        )
    errors += [item["message"] for item in findings if item["severity"] == "error"]
    warnings += [item["message"] for item in findings if item["severity"] == "warning"]
    overlapping: list[dict[str, JsonValue]] = []
    if draft.effective_from:
        statement = select(RuleSet).where(
            RuleSet.scheme_id == scheme_id,
            RuleSet.approval_status == "APPROVED",
            or_(RuleSet.effective_to.is_(None), RuleSet.effective_to >= draft.effective_from),
        )
        if draft.effective_to:
            statement = statement.where(RuleSet.effective_from <= draft.effective_to)
        overlaps = list(await session.scalars(statement.order_by(RuleSet.version_number)))
        overlapping = [
            {
                "id": str(item.id),
                "version_number": item.version_number,
                "title": item.title,
                "effective_from": item.effective_from.isoformat(),
                "effective_to": item.effective_to.isoformat() if item.effective_to else None,
                "scope_note": item.scope_note,
            }
            for item in overlaps
        ]
        if set(draft.replaces_rule_set_ids) != {item.id for item in overlaps} or len(
            set(draft.replaces_rule_set_ids)
        ) != len(draft.replaces_rule_set_ids):
            errors.append(
                "Explicitly review and list every overlapping approved version; the current replacement list does not match."
            )
        if overlaps and len(draft.replacement_notes.strip()) < 20:
            errors.append(
                "Explain the reviewed date/applicability relationship to every overlapping version."
            )
    return (
        DraftValidation(
            publishable=not errors,
            errors=list(dict.fromkeys(errors)),
            warnings=list(dict.fromkeys(warnings)),
            overlapping_rule_sets=overlapping,
        ),
        program,
        findings,
    )
