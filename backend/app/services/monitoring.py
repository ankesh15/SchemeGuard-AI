"""Opt-in monitoring reuses official acquisition, parsing and Phase 4 review."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.proposals import source_pages
from app.auth.security import Administrator
from app.core.config import Settings
from app.ingestion.fetcher import fetch_pdf_response
from app.ingestion.storage import document_storage
from app.ingestion.text_processor import normalize
from app.models import (
    AgentWorkflow,
    BackgroundJob,
    DocumentVersion,
    MonitoringRun,
    PolicyChange,
    PolicyChangeDetail,
    PolicyReview,
    RuleSet,
    SourceMonitor,
    User,
)
from app.repositories.rule import RuleRepository
from app.services.ingestion import approved_source, process_document, register_document
from app.services.jobs import enqueue


def next_check(monitor: SourceMonitor, now: datetime) -> datetime:
    value = now.replace(hour=monitor.hour_utc, minute=0, second=0, microsecond=0)
    if monitor.frequency == "weekly":
        value += timedelta(days=(monitor.weekday - value.weekday()) % 7)
    if value <= now:
        value += timedelta(days=7 if monitor.frequency == "weekly" else 1)
    return max(value, now + timedelta(seconds=monitor.min_interval_seconds))


async def queue_monitor(session: AsyncSession, monitor: SourceMonitor, key: str) -> UUID:
    if not monitor.enabled:
        raise HTTPException(409, "Monitoring is disabled for this source")
    await approved_source(session, monitor.source_id)
    running = await session.scalar(
        select(MonitoringRun)
        .where(MonitoringRun.monitor_id == monitor.id, MonitoringRun.status.in_(["QUEUED", "RUNNING"]))
        .order_by(MonitoringRun.created_at.desc())
        .limit(1)
    )
    if running:
        return running.job_id
    now = datetime.now(UTC)
    if (
        monitor.last_started_at
        and monitor.last_started_at + timedelta(seconds=monitor.min_interval_seconds) > now
    ):
        raise HTTPException(429, "This source's minimum check interval has not elapsed")
    job_id = await enqueue(session, "MONITOR", key, {"monitor_id": str(monitor.id)})
    identifier = uuid5(job_id, "monitoring-run")
    if not await session.get(MonitoringRun, identifier):
        session.add(MonitoringRun(id=identifier, monitor_id=monitor.id, job_id=job_id))
    return job_id


async def schedule_due(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    monitors = list(
        await session.scalars(
            select(SourceMonitor)
            .where(SourceMonitor.enabled.is_(True), SourceMonitor.next_check_at <= now)
            .with_for_update(skip_locked=True)
            .limit(50)
        )
    )
    count = 0
    for monitor in monitors:
        try:
            await queue_monitor(
                session, monitor, f"scheduled:{monitor.id}:{monitor.next_check_at.isoformat()}"
            )
            count += 1
        except HTTPException as error:
            if error.status_code not in {403, 409, 429}:
                raise
            if error.status_code == 403:
                monitor.verification_status = "POTENTIALLY_OUTDATED"
        monitor.next_check_at = next_check(monitor, now)
    await session.commit()
    return count


async def monitor_document(session: AsyncSession, settings: Settings, job: BackgroundJob) -> dict[str, Any]:
    monitor = await session.get(SourceMonitor, UUID(job.payload["monitor_id"]))
    if not monitor or not monitor.enabled:
        return {"skipped": "monitor_disabled"}
    source = await approved_source(session, monitor.source_id)
    user = await session.get(User, monitor.created_by)
    if not user or not user.is_active or user.role != "admin":
        raise ValueError("Monitoring requires an active approving administrator")
    run = await session.scalar(select(MonitoringRun).where(MonitoringRun.job_id == job.id))
    assert run is not None
    if run.status in {"CHANGED", "UNCHANGED"}:
        return {"run_id": str(run.id), "status": run.status}
    now = datetime.now(UTC)
    latest = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.source_id == source.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    old_id = monitor.last_document_id or (latest.id if latest else None)
    run.old_document_id = old_id
    run.status = "RUNNING"
    monitor.last_started_at = now
    await session.commit()
    # Periodically bypass validators: a checksum is authoritative, not a header.
    use_validators = bool(old_id and job.attempts == 1 and now.weekday() != 6)
    response = await fetch_pdf_response(
        source.url,
        settings.pdf_max_bytes,
        settings.document_download_timeout,
        monitor.etag if use_validators else None,
        monitor.last_modified if use_validators else None,
    )
    run.response_status = response.status
    if response.status == 304:
        original = await session.get(DocumentVersion, old_id)
        if not original or original.source_id != source.id:
            raise ValueError("A 304 response needs an existing exact-source version")
        # Also verifies preservation and checksum before accepting a header hit.
        import asyncio

        await asyncio.to_thread(
            document_storage(settings).read,
            original.storage_key,
            original.content_sha256,
            settings.pdf_max_bytes,
        )
        new_id = original.id
    else:
        administrator = Administrator(user.id, user.username, now + timedelta(minutes=10), "")
        document, _ = await register_document(
            session, settings, administrator, source.id, response.content, response.filename, "download", None
        )
        new_id = document.id
        monitor.etag = response.etag
        monitor.last_modified = response.last_modified
    run.new_document_id = new_id
    run.status = "UNCHANGED" if new_id == old_id else "CHANGED"
    run.finished_at = datetime.now(UTC)
    run.error_code = None
    monitor.last_success_at = run.finished_at
    monitor.last_document_id = new_id
    monitor.next_check_at = next_check(monitor, run.finished_at)
    if run.status == "CHANGED":
        monitor.verification_status = "POTENTIALLY_OUTDATED"
        change_id = uuid5(run.id, "policy-change")
        if not await session.get(PolicyChange, change_id):
            old_rule = await RuleRepository(session).approved_for(source.scheme_id, now.date())
            session.add(
                PolicyChange(
                    id=change_id,
                    scheme_id=source.scheme_id,
                    source_id=source.id,
                    run_id=run.id,
                    old_document_id=old_id,
                    new_document_id=new_id,
                    old_rule_set_id=old_rule.id if old_rule else None,
                )
            )
            await session.flush()
        await enqueue(session, "DOCUMENT", f"document-change:{change_id}", {"change_id": str(change_id)})
    await session.commit()
    return {"run_id": str(run.id), "status": run.status, "document_version_id": str(new_id)}


async def process_change_document(
    session: AsyncSession, settings: Settings, job: BackgroundJob, runner: Any = None
) -> dict[str, Any]:
    change = await session.get(PolicyChange, UUID(job.payload["change_id"]))
    assert change is not None
    monitor = await session.scalar(select(SourceMonitor).where(SourceMonitor.source_id == change.source_id))
    assert monitor is not None
    await approved_source(session, change.source_id)
    user = await session.get(User, monitor.created_by)
    if not user or not user.is_active or user.role != "admin":
        raise ValueError("Administrator unavailable")
    administrator = Administrator(user.id, user.username, datetime.now(UTC) + timedelta(minutes=10), "")
    await process_document(
        session,
        settings,
        administrator,
        change.new_document_id,
        "parse_only",
        job_id=uuid5(change.id, "parse"),
    )
    new_pages = await source_pages(session, change.new_document_id)
    old_pages = await source_pages(session, change.old_document_id) if change.old_document_id else {}
    if (
        old_pages
        and all(not page.issues for page in [*old_pages.values(), *new_pages.values()])
        and normalize(" ".join(page.text_content for page in old_pages.values()))
        == normalize(" ".join(page.text_content for page in new_pages.values()))
    ):
        change.classification = "FORMATTING"
        change.verification_status = "NO_POLICY_CHANGE"
        await session.commit()
        return {"classification": "FORMATTING", "ai_skipped": True}
    workflow_id = uuid5(change.id, "workflow")
    if not await session.get(AgentWorkflow, workflow_id):
        session.add(
            AgentWorkflow(
                id=workflow_id,
                document_version_id=change.new_document_id,
                requested_by=user.id,
                request_key=workflow_id,
                request_fingerprint=hashlib.sha256(str(change.id).encode()).hexdigest(),
            )
        )
        await session.flush()
    change.workflow_id = workflow_id
    await session.commit()
    if runner is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.agents.graph import WorkflowRunner

        runner = WorkflowRunner(settings, async_sessionmaker(session.bind, expire_on_commit=False))
    await runner.run(workflow_id)
    workflow = await session.get(AgentWorkflow, workflow_id, populate_existing=True)
    if not workflow or workflow.status == "FAILED":
        raise ValueError("Document workflow requires recovery; last approved policy remains active")
    await enqueue(session, "COMPARE", f"compare:{change.id}:initial", {"change_id": str(change.id)})
    await session.commit()
    return {"workflow_id": str(workflow_id), "status": workflow.status}


async def compare_change(session: AsyncSession, identifier: UUID, *, verified: bool = False) -> PolicyChange:
    from app.agents.review import current_revision
    from app.services.policy_diff import compare_policies

    change = await session.get(PolicyChange, identifier)
    if not change:
        raise HTTPException(404, "Policy change not found")
    if change.verification_status in {"APPROVED", "REJECTED"}:
        return change
    review = await session.scalar(select(PolicyReview).where(PolicyReview.workflow_id == change.workflow_id))
    if not review:
        return change
    revision = await current_revision(session, review)
    if change.compared_revision == revision.revision_number and not verified:
        return change
    old = []
    old_logic = "and"
    if change.old_rule_set_id:
        old_rule = await RuleRepository(session).by_id(change.old_rule_set_id)
        if old_rule:
            old_logic = old_rule.logical_operator
            for condition in old_rule.conditions:
                old.append(
                    {
                        "key": condition.condition_key,
                        "label": condition.label,
                        "expression": condition.expression,
                        "evidence": [
                            {
                                "document_version_id": str(item.document_version_id),
                                "locator": item.locator,
                                "excerpt": item.excerpt,
                            }
                            for item in condition.evidence
                        ],
                    }
                )
    classification, details = compare_policies(
        old,
        revision.proposal["conditions"],
        old_logic=old_logic,
        new_logic=revision.proposal["logical_operator"],
        complete=verified,
    )
    from app.services.policy_diff import compare_document_facts

    old_pages = await source_pages(session, change.old_document_id) if change.old_document_id else {}
    new_pages = await source_pages(session, change.new_document_id)
    fact_details = compare_document_facts(
        [
            {
                "document_version_id": str(change.old_document_id),
                "page_number": page.page_number,
                "text": page.text_content,
            }
            for page in old_pages.values()
        ],
        [
            {
                "document_version_id": str(change.new_document_id),
                "page_number": page.page_number,
                "text": page.text_content,
            }
            for page in new_pages.values()
        ],
    )
    details += fact_details
    if fact_details:
        classification = (
            "INCONCLUSIVE"
            if any(item["change_type"] == "INCONCLUSIVE_DOCUMENT_FACT" for item in fact_details)
            else "MATERIAL"
        )
    change.classification = classification
    change.compared_revision = revision.revision_number
    for index, detail in enumerate(details):
        session.add(
            PolicyChangeDetail(
                id=uuid5(change.id, f"detail:{revision.revision_number}:{verified}:{index}"),
                change_id=change.id,
                revision_number=revision.revision_number,
                condition_key=("verified:" if verified else "") + str(detail["condition_id"])[:180],
                detail=detail,
            )
        )
    await session.flush()
    return change


async def record_publication(session: AsyncSession, workflow_id: UUID, rule: RuleSet, reviewer: UUID) -> None:
    change = await session.scalar(
        select(PolicyChange).where(PolicyChange.workflow_id == workflow_id).with_for_update()
    )
    if not change:
        return
    await compare_change(session, change.id, verified=True)
    if change.clarification_revision and change.compared_revision <= change.clarification_revision:
        raise ValueError("Clarification requires a new saved review revision")
    change.verification_status = "APPROVED"
    change.new_rule_set_id = rule.id
    change.effective_from = rule.effective_from
    change.reviewer_id = reviewer
    change.approved_at = rule.approved_at
    from app.services.reassessment import queue_reassessment

    await queue_reassessment(session, change)
    # Clear currency only for the latest observed version, never an old proposal.
    monitor = await session.scalar(select(SourceMonitor).where(SourceMonitor.source_id == change.source_id))
    if monitor and monitor.last_document_id == change.new_document_id:
        monitor.verification_status = "VERIFIED"
