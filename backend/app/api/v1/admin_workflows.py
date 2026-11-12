import hashlib
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import WorkflowRunner, event, workflow_lock
from app.agents.review import current_revision, decide, save_revision, validation_context
from app.auth.security import Administrator, audit, limit, require_admin
from app.core.database import get_session
from app.models import (
    AgentWorkflow,
    PolicyReview,
    ProcessingJob,
    ReviewDecision,
    ReviewRevision,
    WorkflowEvent,
)
from app.rag.embeddings import EmbeddingError, EmbeddingProvider, embedding_provider, index_document
from app.schemas.workflow import (
    ApprovalRequest,
    CancellationRequest,
    PolicyDraft,
    RejectionRequest,
    RevisionRequest,
    WorkflowCreate,
)
from app.services.ingestion import get_document

router = APIRouter(prefix="/admin", tags=["administrator policy workflows"])
DB = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[Administrator, Depends(require_admin)]
Status = Literal["PROCESSING", "PENDING_REVIEW", "APPROVED", "REJECTED", "FAILED", "CANCELLED"]


def get_runner(request: Request) -> WorkflowRunner:
    return request.app.state.workflow_runner  # type: ignore[no-any-return]


def get_embeddings(request: Request) -> EmbeddingProvider:
    return embedding_provider(request.app.state.settings)


Runner = Annotated[WorkflowRunner, Depends(get_runner)]
Embeddings = Annotated[EmbeddingProvider, Depends(get_embeddings)]


async def workflow_view(session: AsyncSession, workflow: AgentWorkflow) -> dict[str, Any]:
    review = await session.scalar(select(PolicyReview).where(PolicyReview.workflow_id == workflow.id))
    document = await get_document(session, workflow.document_version_id)
    job = await session.get(ProcessingJob, workflow.extraction_job_id) if workflow.extraction_job_id else None
    return {
        "id": str(workflow.id),
        "thread_id": str(workflow.id),
        "graph_version": workflow.graph_version,
        "document_version_id": str(workflow.document_version_id),
        "scheme_id": str(document.scheme_id),
        "scheme_name": document.scheme_name,
        "document_filename": document.original_filename,
        "status": workflow.status,
        "stage": workflow.stage,
        "attempts": workflow.attempts,
        "extraction_job_id": str(workflow.extraction_job_id) if workflow.extraction_job_id else None,
        "provider": job.provider if job else "gemini",
        "model": job.model if job else None,
        "review_id": str(review.id) if review else None,
        "published_rule_set_id": str(workflow.published_rule_set_id)
        if workflow.published_rule_set_id
        else None,
        "error_code": workflow.error_code,
        "error_message": workflow.error_message,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
    }


@router.post("/workflows", status_code=201)
async def create_workflow(
    body: WorkflowCreate, request: Request, administrator: Admin, session: DB, runner: Runner
) -> dict[str, Any]:
    await limit(session, f"workflows:{administrator.id}", 10, 900)
    document = await get_document(session, body.document_version_id)
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    workflow = await session.scalar(
        select(AgentWorkflow).where(
            AgentWorkflow.requested_by == administrator.id, AgentWorkflow.request_key == body.request_key
        )
    )
    if workflow:
        if workflow.request_fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key was used for a different workflow request")
        return await workflow_view(session, workflow)
    if body.extraction_job_id:
        job = await session.get(ProcessingJob, body.extraction_job_id)
        if (
            not job
            or job.document_version_id != document.id
            or job.status not in {"PENDING_REVIEW", "INCOMPLETE"}
            or job.candidate_count < 1
        ):
            raise HTTPException(
                422, "Choose a successful candidate extraction from this exact document version"
            )
    workflow = AgentWorkflow(
        document_version_id=document.id,
        requested_by=administrator.id,
        request_key=body.request_key,
        request_fingerprint=fingerprint,
        extraction_job_id=body.extraction_job_id,
    )
    session.add(workflow)
    audit(session, "policy_workflow_created", administrator.id, str(document.id))
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            409, "A workflow with this idempotency key already exists; reload its status"
        ) from error
    async with request.app.state.document_slots:
        await runner.run(workflow.id)
    await session.refresh(workflow)
    return await workflow_view(session, workflow)


@router.get("/workflows")
async def workflows(
    administrator: Admin,
    session: DB,
    status: Status | None = None,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(AgentWorkflow)
    if status:
        statement = statement.where(AgentWorkflow.status == status)
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = await session.scalars(
        statement.order_by(AgentWorkflow.created_at.desc(), AgentWorkflow.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [await workflow_view(session, row) for row in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/workflows/{identifier}")
async def workflow_detail(identifier: UUID, administrator: Admin, session: DB) -> dict[str, Any]:
    workflow = await session.get(AgentWorkflow, identifier)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    events = await session.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_id == identifier)
        .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        .limit(200)
    )
    return {
        **await workflow_view(session, workflow),
        "history": [
            {
                "id": str(item.id),
                "stage": item.stage,
                "event": item.event,
                "details": item.details,
                "created_at": item.created_at.isoformat(),
            }
            for item in events
        ],
    }


@router.post("/workflows/{identifier}/resume")
async def resume_workflow(
    identifier: UUID,
    body: CancellationRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    workflow = await session.get(AgentWorkflow, identifier)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    await limit(session, f"workflow-resume:{administrator.id}", 10, 900)
    audit(session, "policy_workflow_resume_requested", administrator.id, str(identifier), notes=body.notes)
    await session.commit()
    async with request.app.state.document_slots:
        await runner.run(identifier)
    await session.refresh(workflow)
    return await workflow_view(session, workflow)


@router.post("/workflows/{identifier}/cancel")
async def cancel_workflow(
    identifier: UUID, body: CancellationRequest, request: Request, administrator: Admin, session: DB
) -> dict[str, Any]:
    async with workflow_lock(request.app.state.settings, identifier):
        workflow = await session.get(AgentWorkflow, identifier)
        if not workflow:
            raise HTTPException(404, "Workflow not found")
        review = await session.scalar(select(PolicyReview).where(PolicyReview.workflow_id == identifier))
        decision = (
            await session.scalar(select(ReviewDecision.id).where(ReviewDecision.review_id == review.id))
            if review
            else None
        )
        if (
            workflow.status in {"APPROVED", "REJECTED", "CANCELLED"}
            or decision
            or workflow.published_rule_set_id
        ):
            raise HTTPException(409, "A decided, published, or cancelled workflow cannot be cancelled")
        workflow.status = "CANCELLED"
        if review:
            review.status = "CANCELLED"
        await event(
            session, workflow, "cancelled", "administrator_cancelled", reviewer_id=str(administrator.id)
        )
        audit(session, "policy_workflow_cancelled", administrator.id, str(identifier), notes=body.notes)
        await session.commit()
        return await workflow_view(session, workflow)


@router.get("/reviews")
async def reviews(
    administrator: Admin,
    session: DB,
    status: Literal["PENDING_REVIEW", "APPROVED", "REJECTED", "CANCELLED", "ALL"] | None = "PENDING_REVIEW",
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(PolicyReview)
    if status and status != "ALL":
        statement = statement.where(PolicyReview.status == status)
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = await session.scalars(
        statement.order_by(PolicyReview.created_at.desc(), PolicyReview.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for item in records:
        workflow = await session.get(AgentWorkflow, item.workflow_id)
        assert workflow is not None
        items.append(
            {
                "id": str(item.id),
                "status": item.status,
                "revision_number": item.revision_number,
                "created_at": item.created_at.isoformat(),
                "workflow": await workflow_view(session, workflow),
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/reviews/{identifier}")
async def review_detail(identifier: UUID, administrator: Admin, session: DB) -> dict[str, Any]:
    review = await session.get(PolicyReview, identifier)
    if not review:
        raise HTTPException(404, "Policy review not found")
    workflow = await session.get(AgentWorkflow, review.workflow_id)
    assert workflow is not None
    revision = await current_revision(session, review)
    draft = PolicyDraft.model_validate(revision.proposal)
    validation, _, findings = await validation_context(session, review, draft)
    all_findings = list({item["id"]: item for item in review.verification_findings + findings}.values())
    versions = await session.scalars(
        select(ReviewRevision)
        .where(ReviewRevision.review_id == identifier)
        .order_by(ReviewRevision.revision_number)
    )
    decision = await session.scalar(select(ReviewDecision).where(ReviewDecision.review_id == identifier))
    document = await get_document(session, workflow.document_version_id)
    return {
        "id": str(review.id),
        "status": review.status,
        "workflow": await workflow_view(session, workflow),
        "document": document.model_dump(mode="json"),
        "revision_number": revision.revision_number,
        "proposal_sha256": revision.proposal_sha256,
        "draft": draft.model_dump(mode="json"),
        "original_proposal": review.original_proposal,
        "findings": all_findings,
        "required_finding_ids": [item["id"] for item in all_findings if item["severity"] != "info"],
        "validation": validation.model_dump(mode="json"),
        "revision_history": [
            {
                "id": str(item.id),
                "revision_number": item.revision_number,
                "actor_id": str(item.actor_id) if item.actor_id else None,
                "notes": item.notes,
                "proposal_sha256": item.proposal_sha256,
                "created_at": item.created_at.isoformat(),
            }
            for item in versions
        ],
        "decision": {
            "id": str(decision.id),
            "action": decision.action,
            "reviewer_id": str(decision.reviewer_id),
            "notes": decision.notes,
            "created_at": decision.created_at.isoformat(),
        }
        if decision
        else None,
    }


@router.post("/reviews/{identifier}/revisions", status_code=201)
async def edit_review(
    identifier: UUID, body: RevisionRequest, administrator: Admin, session: DB
) -> dict[str, Any]:
    await save_revision(session, identifier, body, administrator)
    return await review_detail(identifier, administrator, session)


async def record_and_resume(
    identifier: UUID,
    body: ApprovalRequest | RejectionRequest,
    request: Request,
    administrator: Administrator,
    session: AsyncSession,
    runner: WorkflowRunner,
) -> dict[str, Any]:
    review = await session.get(PolicyReview, identifier)
    if review is None:
        raise HTTPException(404, "Policy review not found")
    workflow_id = review.workflow_id
    await session.commit()
    async with request.app.state.document_slots:
        async with workflow_lock(request.app.state.settings, workflow_id):
            await decide(session, identifier, body, administrator)
            await runner.run(workflow_id, lock_held=True)
    return await review_detail(identifier, administrator, session)


@router.post("/reviews/{identifier}/approve")
async def approve_review(
    identifier: UUID,
    body: ApprovalRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    await limit(session, f"review-decision:{administrator.id}", 20, 900)
    return await record_and_resume(identifier, body, request, administrator, session, runner)


@router.post("/reviews/{identifier}/reject")
async def reject_review(
    identifier: UUID,
    body: RejectionRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    await limit(session, f"review-decision:{administrator.id}", 20, 900)
    return await record_and_resume(identifier, body, request, administrator, session, runner)


@router.post("/documents/{identifier}/index")
async def index_document_chunks(
    identifier: UUID, request: Request, administrator: Admin, session: DB, embeddings: Embeddings
) -> dict[str, int | str]:
    await get_document(session, identifier)
    await limit(session, f"embedding-index:{administrator.id}", 10, 900)
    async with request.app.state.document_slots:
        try:
            result = await index_document(session, identifier, embeddings, request.app.state.settings)
        except (EmbeddingError, TimeoutError) as error:
            raise HTTPException(
                503, "Embedding indexing is unavailable; original text and workflow history are preserved"
            ) from error
    audit(
        session,
        "document_chunks_indexed",
        administrator.id,
        str(identifier),
        provider=embeddings.name,
        model=embeddings.model,
    )
    await session.commit()
    return result
