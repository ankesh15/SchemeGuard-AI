from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from app.api.v1.admin_workflows import DB, Admin, Runner, record_and_resume
from app.auth.security import audit, limit
from app.models import (
    BackgroundJob,
    ChangeReviewEvent,
    DocumentVersion,
    MonitoringRun,
    PolicyChange,
    PolicyChangeDetail,
    PolicyReview,
    SchemeSource,
    SourceMonitor,
)
from app.schemas.monitoring import ClarificationRequest, MonitorCreate, MonitorPatch
from app.schemas.workflow import ApprovalRequest, RejectionRequest
from app.services.ingestion import approved_source
from app.services.monitoring import compare_change, next_check, queue_monitor

router = APIRouter(tags=["policy monitoring"])


async def monitor_view(session: DB, item: SourceMonitor) -> dict[str, Any]:
    source = await session.get(SchemeSource, item.source_id)
    return {column.name: getattr(item, column.name) for column in SourceMonitor.__table__.columns} | {
        "source_url": source.url if source else None,
        "source_title": source.title if source else None,
    }


@router.get("/admin/monitors")
async def monitors(administrator: Admin, session: DB) -> dict[str, Any]:
    rows = await session.scalars(select(SourceMonitor).order_by(SourceMonitor.created_at.desc()).limit(100))
    return {"items": [await monitor_view(session, row) for row in rows]}


@router.post("/admin/monitors", status_code=201)
async def create_monitor(body: MonitorCreate, administrator: Admin, session: DB) -> dict[str, Any]:
    if not body.access_permitted:
        raise HTTPException(422, "Confirm that scheduled access to this specific official URL is permitted")
    await approved_source(session, body.source_id)
    if await session.scalar(select(SourceMonitor.id).where(SourceMonitor.source_id == body.source_id)):
        raise HTTPException(409, "This source already has a monitoring configuration")
    item = SourceMonitor(**body.model_dump(exclude={"access_permitted"}), created_by=administrator.id)
    session.add(item)
    await session.flush()
    audit(session, "monitor_created", administrator.id, str(item.id))
    await session.commit()
    return await monitor_view(session, item)


@router.patch("/admin/monitors/{identifier}")
async def patch_monitor(
    identifier: UUID, body: MonitorPatch, administrator: Admin, session: DB
) -> dict[str, Any]:
    item = await session.scalar(select(SourceMonitor).where(SourceMonitor.id == identifier).with_for_update())
    if not item:
        raise HTTPException(404, "Monitor not found")
    await approved_source(session, item.source_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    item.next_check_at = next_check(item, datetime.now(UTC))
    audit(session, "monitor_updated", administrator.id, str(item.id))
    await session.commit()
    return await monitor_view(session, item)


@router.post("/admin/monitors/{identifier}/check", status_code=202)
async def check_monitor(identifier: UUID, administrator: Admin, session: DB) -> dict[str, str]:
    await limit(session, f"monitor-check:{administrator.id}", 20, 900)
    item = await session.scalar(select(SourceMonitor).where(SourceMonitor.id == identifier).with_for_update())
    if not item:
        raise HTTPException(404, "Monitor not found")
    job_id = await queue_monitor(session, item, f"manual:{identifier}:{uuid4()}")
    audit(session, "monitor_check_queued", administrator.id, str(identifier))
    await session.commit()
    return {"job_id": str(job_id), "status": "QUEUED"}


@router.get("/admin/monitoring-runs")
async def monitoring_runs(
    administrator: Admin, session: DB, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(MonitoringRun, BackgroundJob)
            .join(BackgroundJob, BackgroundJob.id == MonitoringRun.job_id)
            .order_by(MonitoringRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "items": [
            {
                **{column.name: getattr(run, column.name) for column in MonitoringRun.__table__.columns},
                "job_status": job.status,
                "attempts": job.attempts,
                "error_code": job.error_code,
                "available_at": job.available_at,
            }
            for run, job in rows
        ],
        "total": await session.scalar(select(func.count()).select_from(MonitoringRun)),
        "page": page,
        "page_size": page_size,
    }


async def change_view(session: DB, change: PolicyChange, detailed: bool = False) -> dict[str, Any]:
    source = await session.get(SchemeSource, change.source_id)
    result = {column.name: getattr(change, column.name) for column in PolicyChange.__table__.columns} | {
        "source_url": source.url if source else None,
        "source_title": source.title if source else None,
    }
    if detailed:
        await compare_change(session, change.id)
        rows = await session.scalars(
            select(PolicyChangeDetail)
            .where(
                PolicyChangeDetail.change_id == change.id,
                PolicyChangeDetail.revision_number == change.compared_revision,
            )
            .order_by(PolicyChangeDetail.condition_key)
        )
        result["details"] = [
            row.detail
            for row in rows
            if row.condition_key.startswith("verified:") == (change.verification_status == "APPROVED")
        ]
        review = await session.scalar(
            select(PolicyReview).where(PolicyReview.workflow_id == change.workflow_id)
        )
        result["review_id"] = str(review.id) if review else None
        result["review_events"] = [
            {
                "action": row.action,
                "notes": row.notes,
                "actor_id": str(row.actor_id),
                "created_at": row.created_at,
            }
            for row in await session.scalars(
                select(ChangeReviewEvent)
                .where(ChangeReviewEvent.change_id == change.id)
                .order_by(ChangeReviewEvent.created_at)
            )
        ]
        result["documents"] = [
            {
                "id": str(row.id),
                "version_number": row.version_number,
                "checksum": row.content_sha256,
                "retrieved_at": row.retrieved_at,
            }
            for row in await session.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.id.in_(
                        [value for value in [change.old_document_id, change.new_document_id] if value]
                    )
                )
            )
        ]
    return result


@router.get("/admin/policy-changes")
async def policy_changes(
    administrator: Admin,
    session: DB,
    status: str | None = Query(
        None, pattern="^(PENDING_REVIEW|APPROVED|REJECTED|CLARIFICATION|NO_POLICY_CHANGE)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(PolicyChange)
    if status:
        statement = statement.where(PolicyChange.verification_status == status)
    rows = await session.scalars(
        statement.order_by(PolicyChange.detected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return {
        "items": [await change_view(session, row) for row in rows],
        "total": await session.scalar(select(func.count()).select_from(statement.subquery())),
        "page": page,
        "page_size": page_size,
    }


@router.get("/admin/policy-changes/{identifier}")
async def get_change(identifier: UUID, administrator: Admin, session: DB) -> dict[str, Any]:
    item = await session.get(PolicyChange, identifier)
    if not item:
        raise HTTPException(404, "Policy change not found")
    result = await change_view(session, item, True)
    await session.commit()
    return result


@router.post("/admin/policy-changes/{identifier}/clarify")
async def clarify(
    identifier: UUID, body: ClarificationRequest, administrator: Admin, session: DB
) -> dict[str, Any]:
    change = await session.scalar(select(PolicyChange).where(PolicyChange.id == identifier).with_for_update())
    if not change or change.verification_status in {"APPROVED", "REJECTED"}:
        raise HTTPException(409, "Only undecided changes can request clarification")
    await compare_change(session, identifier)
    change.verification_status = "CLARIFICATION"
    change.clarification_revision = change.compared_revision
    session.add(
        ChangeReviewEvent(
            change_id=identifier,
            actor_id=administrator.id,
            action="CLARIFICATION",
            notes=body.notes,
            revision_number=change.compared_revision,
        )
    )
    audit(session, "policy_change_clarification", administrator.id, str(identifier))
    await session.commit()
    return await change_view(session, change)


async def decide_change(
    identifier: UUID,
    body: ApprovalRequest | RejectionRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    change = await session.get(PolicyChange, identifier)
    if not change:
        raise HTTPException(404, "Policy change not found")
    review = await session.scalar(select(PolicyReview).where(PolicyReview.workflow_id == change.workflow_id))
    if not review:
        raise HTTPException(409, "The extraction workflow has no reviewable proposal yet")
    if (
        isinstance(body, ApprovalRequest)
        and change.clarification_revision
        and review.revision_number <= change.clarification_revision
    ):
        raise HTTPException(409, "Save a new revision resolving the clarification before approving")
    await record_and_resume(review.id, body, request, administrator, session, runner)
    await session.refresh(change)
    if isinstance(body, RejectionRequest):
        change.verification_status = "REJECTED"
        change.reviewer_id = administrator.id
    session.add(
        ChangeReviewEvent(
            change_id=identifier,
            actor_id=administrator.id,
            action="APPROVE" if isinstance(body, ApprovalRequest) else "REJECT",
            notes=body.notes,
            revision_number=body.expected_revision,
        )
    )
    await session.commit()
    return await change_view(session, change, True)


@router.post("/admin/policy-changes/{identifier}/approve")
async def approve_change(
    identifier: UUID,
    body: ApprovalRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    return await decide_change(identifier, body, request, administrator, session, runner)


@router.post("/admin/policy-changes/{identifier}/reject")
async def reject_change(
    identifier: UUID,
    body: RejectionRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    runner: Runner,
) -> dict[str, Any]:
    return await decide_change(identifier, body, request, administrator, session, runner)


@router.get("/policy-updates")
async def published_changes(
    session: DB,
    scheme_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(PolicyChange).where(
        PolicyChange.verification_status == "APPROVED", PolicyChange.new_rule_set_id.is_not(None)
    )
    if scheme_id:
        statement = statement.where(PolicyChange.scheme_id == scheme_id)
    rows = await session.scalars(
        statement.order_by(PolicyChange.approved_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for item in rows:
        source = await session.get(SchemeSource, item.source_id)
        items.append(
            {
                "id": str(item.id),
                "scheme_id": str(item.scheme_id),
                "source_url": source.url if source else None,
                "old_rule_set_id": str(item.old_rule_set_id) if item.old_rule_set_id else None,
                "new_rule_set_id": str(item.new_rule_set_id),
                "effective_from": item.effective_from,
                "published_at": item.approved_at,
                "classification": item.classification,
                "notice": "Verified policy publication; not official individual eligibility approval.",
            }
        )
    return {
        "items": items,
        "total": await session.scalar(select(func.count()).select_from(statement.subquery())),
        "page": page,
        "page_size": page_size,
    }
