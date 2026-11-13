"""Immutable human-review revisions and single-use authenticated decisions."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.proposals import proposal_digest, validate_draft
from app.auth.security import Administrator, audit
from app.models import (
    AgentWorkflow,
    DocumentAsset,
    DocumentVersion,
    PolicyReview,
    ReviewDecision,
    ReviewRevision,
    RuleCandidate,
    SchemeSource,
)
from app.schemas.workflow import ApprovalRequest, PolicyDraft, RejectionRequest, RevisionRequest


async def current_revision(session: AsyncSession, review: PolicyReview) -> ReviewRevision:
    revision = await session.scalar(
        select(ReviewRevision).where(
            ReviewRevision.review_id == review.id, ReviewRevision.revision_number == review.revision_number
        )
    )
    if revision is None:
        raise HTTPException(503, "Review revision is unavailable")
    return revision


async def validation_context(
    session: AsyncSession, review: PolicyReview, draft: PolicyDraft
) -> tuple[Any, Any, list[dict[str, Any]]]:
    workflow = await session.get(AgentWorkflow, review.workflow_id)
    assert workflow is not None
    document = await session.get(DocumentVersion, workflow.document_version_id)
    assert document is not None
    source = await session.get(SchemeSource, document.source_id)
    assert source is not None
    candidate_ids = set(
        await session.scalars(
            select(RuleCandidate.id).where(RuleCandidate.job_id == workflow.extraction_job_id)
        )
    )
    return await validate_draft(session, draft, document.id, source.scheme_id, candidate_ids)


async def save_revision(
    session: AsyncSession, identifier: UUID, body: RevisionRequest, administrator: Administrator
) -> PolicyReview:
    review = await session.scalar(
        select(PolicyReview)
        .where(PolicyReview.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if review is None:
        raise HTTPException(404, "Policy review not found")
    if review.status != "PENDING_REVIEW" or review.revision_number != body.expected_revision:
        raise HTTPException(409, "Review changed or already decided; reload before editing")
    review.revision_number += 1
    session.add(
        ReviewRevision(
            review_id=review.id,
            revision_number=review.revision_number,
            actor_id=administrator.id,
            proposal=body.draft.model_dump(mode="json"),
            proposal_sha256=proposal_digest(body.draft),
            notes=body.notes,
        )
    )
    audit(session, "policy_review_edited", administrator.id, str(review.id), revision=review.revision_number)
    await session.commit()
    return review


async def decide(
    session: AsyncSession,
    identifier: UUID,
    body: ApprovalRequest | RejectionRequest,
    administrator: Administrator,
) -> ReviewDecision:
    review = await session.scalar(
        select(PolicyReview)
        .where(PolicyReview.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if review is None:
        raise HTTPException(404, "Policy review not found")
    if (
        review.status != "PENDING_REVIEW"
        or review.revision_number != body.expected_revision
        or await session.scalar(select(ReviewDecision.id).where(ReviewDecision.review_id == review.id))
    ):
        raise HTTPException(409, "This proposal changed or already has a recorded decision")
    workflow = await session.get(AgentWorkflow, review.workflow_id)
    assert workflow is not None
    if workflow.status != "PENDING_REVIEW":
        raise HTTPException(409, "Workflow is not waiting at its human review checkpoint")
    revision = await current_revision(session, review)
    from app.models import PolicyChange

    change = await session.scalar(select(PolicyChange).where(PolicyChange.workflow_id == workflow.id))
    if (
        isinstance(body, ApprovalRequest)
        and change
        and change.clarification_revision
        and review.revision_number <= change.clarification_revision
    ):
        raise HTTPException(409, "Save a new revision resolving the requested clarification before approval")
    attestations: dict[str, Any] = {}
    action = "REJECT"
    if isinstance(body, ApprovalRequest):
        if body.proposal_sha256 != revision.proposal_sha256:
            raise HTTPException(409, "Approval must reference the exact saved proposal digest")
        if not (
            body.human_review_confirmed and body.complete_policy_confirmed and body.applicability_confirmed
        ):
            raise HTTPException(
                422,
                "Actual human review, complete-policy coverage, and applicability confirmation are required",
            )
        asset = await session.get(DocumentAsset, workflow.document_version_id)
        if (
            not asset
            or set(body.reviewed_pages) != set(range(1, asset.page_count + 1))
            or len(set(body.reviewed_pages)) != len(body.reviewed_pages)
        ):
            raise HTTPException(422, "Confirm inspection of every original document page exactly once")
        draft = PolicyDraft.model_validate(revision.proposal)
        validation, _, findings = await validation_context(session, review, draft)
        if not validation.publishable:
            raise HTTPException(
                422, {"message": "The complete policy is not publishable", "errors": validation.errors}
            )
        required = {
            item["id"] for item in review.verification_findings + findings if item["severity"] != "info"
        }
        if not required <= set(body.acknowledged_findings):
            raise HTTPException(
                422,
                "Review and acknowledge every verification finding; record its resolution in approval notes",
            )
        attestations = body.model_dump(mode="json", exclude={"notes", "proposal_sha256", "expected_revision"})
        action = "APPROVE"
    decision = ReviewDecision(
        review_id=review.id,
        revision_id=revision.id,
        reviewer_id=administrator.id,
        action=action,
        notes=body.notes,
        attestations=attestations,
    )
    session.add(decision)
    if action == "REJECT" and change:
        from app.services.monitoring import compare_change

        await compare_change(session, change.id)
        change.verification_status = "REJECTED"
        change.reviewer_id = administrator.id
    review.status = "APPROVED" if action == "APPROVE" else "REJECTED"
    workflow.status, workflow.updated_at = "PROCESSING", datetime.now(UTC)
    audit(
        session,
        "policy_review_approved" if action == "APPROVE" else "policy_review_rejected",
        administrator.id,
        str(review.id),
        revision=revision.revision_number,
    )
    await session.commit()
    return decision
