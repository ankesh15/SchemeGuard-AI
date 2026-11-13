"""Idempotent publication of an exact, human-approved immutable revision."""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.proposals import proposal_digest
from app.agents.review import validation_context
from app.auth.security import audit
from app.core.config import Settings
from app.ingestion.storage import DocumentStorage
from app.models import (
    AgentWorkflow,
    DocumentVersion,
    PolicyReview,
    ReviewDecision,
    ReviewRevision,
    RuleCondition,
    RuleEvidence,
    RulePublication,
    RuleSet,
    Scheme,
    SchemeSource,
    User,
)
from app.schemas.workflow import PolicyDraft
from app.services.ingestion import approved_source


async def publish(session: AsyncSession, settings: Settings, workflow_id: UUID, decision_id: UUID) -> RuleSet:
    workflow = await session.get(AgentWorkflow, workflow_id)
    decision = await session.get(ReviewDecision, decision_id)
    if not workflow or not decision or decision.action != "APPROVE":
        raise ValueError("Publication requires a persisted human approval")
    review = await session.get(PolicyReview, decision.review_id)
    if not review or review.workflow_id != workflow.id:
        raise ValueError("Approval belongs to a different workflow")
    revision = await session.get(ReviewRevision, decision.revision_id)
    assert revision is not None
    document = await session.get(DocumentVersion, workflow.document_version_id)
    assert document is not None
    source = await session.get(SchemeSource, document.source_id)
    assert source is not None
    await session.execute(select(Scheme.id).where(Scheme.id == source.scheme_id).with_for_update())
    previous = await session.scalar(select(RulePublication).where(RulePublication.workflow_id == workflow.id))
    if previous:
        rule_set = await session.get(RuleSet, previous.rule_set_id)
        assert rule_set is not None
        return rule_set
    reviewer = await session.get(User, decision.reviewer_id)
    if not reviewer or not reviewer.is_active or reviewer.role != "admin":
        raise ValueError("The approving reviewer is no longer an active administrator")
    await approved_source(session, source.id)
    await asyncio.to_thread(
        DocumentStorage(settings.document_storage_root).read,
        document.storage_key,
        document.content_sha256,
        settings.pdf_max_bytes,
    )
    draft = PolicyDraft.model_validate(revision.proposal)
    if proposal_digest(draft) != revision.proposal_sha256:
        raise ValueError("Approved proposal digest mismatch")
    validation, program, _ = await validation_context(session, review, draft)
    if not validation.publishable or program is None or draft.effective_from is None:
        raise ValueError(
            "The approved policy no longer passes complete validation; a new human review is required"
        )
    version = (
        await session.scalar(
            select(func.max(RuleSet.version_number)).where(RuleSet.scheme_id == source.scheme_id)
        )
        or 0
    ) + 1
    identifier = uuid5(workflow.id, "published-rule-set")
    rule_set = RuleSet(
        id=identifier,
        scheme_id=source.scheme_id,
        version_number=version,
        title=draft.title,
        logical_operator=draft.logical_operator,
        effective_from=draft.effective_from,
        effective_to=draft.effective_to,
        source_document_version_id=document.id,
        profile_fields=[field.model_dump(mode="json") for field in draft.profile_fields],
        scope_note=draft.scope_note
        + "\nApplicability review: "
        + draft.applicability_note
        + "\nEffective-date basis: "
        + draft.effective_date_basis
        + ". "
        + draft.effective_date_note,
    )
    session.add(rule_set)
    await session.flush()
    for position, condition in enumerate(draft.conditions):
        row = RuleCondition(
            id=uuid5(identifier, condition.key),
            rule_set_id=identifier,
            condition_key=condition.key,
            label=condition.label,
            position=position,
            expression=condition.expression,
        )
        session.add(row)
        await session.flush()
        seen = set()
        for anchor in condition.evidence:
            quote_hash = hashlib.sha256(anchor.excerpt.encode()).hexdigest()[:12]
            locator = f"page:{anchor.page_number};node:{anchor.node_key};excerpt:{quote_hash}"
            if locator in seen:
                continue
            seen.add(locator)
            session.add(
                RuleEvidence(
                    rule_set_id=identifier,
                    condition_id=row.id,
                    document_version_id=document.id,
                    locator=locator,
                    excerpt=anchor.excerpt,
                )
            )
        await session.flush()
    rule_set.approval_status = "APPROVED"
    rule_set.approved_at = datetime.now(UTC)
    rule_set.approved_by = str(reviewer.id)
    rule_set.approval_basis = "human_review"
    await session.flush()
    session.add(
        RulePublication(
            workflow_id=workflow.id,
            decision_id=decision.id,
            rule_set_id=identifier,
            replaced_rule_set_ids=[str(value) for value in draft.replaces_rule_set_ids],
            applicability_note=draft.applicability_note + "\n" + draft.replacement_notes,
        )
    )
    from app.services.monitoring import record_publication

    await record_publication(session, workflow.id, rule_set, reviewer.id)
    workflow.published_rule_set_id = identifier
    audit(
        session,
        "policy_rule_version_published",
        reviewer.id,
        str(identifier),
        workflow_id=str(workflow.id),
        version=version,
    )
    await session.commit()
    return rule_set
