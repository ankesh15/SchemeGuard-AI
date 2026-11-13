"""PostgreSQL outbox; Redis messages contain only durable job UUIDs."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob


async def enqueue(
    session: AsyncSession,
    kind: str,
    key: str,
    payload: dict[str, Any],
    *,
    available_at: datetime | None = None,
) -> UUID:
    identifier = uuid4()
    statement = (
        insert(BackgroundJob)
        .values(
            id=identifier,
            kind=kind,
            dedupe_key=key,
            payload=payload,
            status="QUEUED",
            attempts=0,
            result={},
            available_at=available_at or datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=[BackgroundJob.dedupe_key])
        .returning(BackgroundJob.id)
    )
    saved = await session.scalar(statement)
    if saved:
        return saved
    existing = await session.scalar(select(BackgroundJob.id).where(BackgroundJob.dedupe_key == key))
    assert existing is not None
    return existing


async def dispatch(session: AsyncSession) -> int:
    from app.workers.celery_app import celery_app

    now = datetime.now(UTC)
    jobs = list(
        await session.scalars(
            select(BackgroundJob)
            .where(
                BackgroundJob.status.in_(["QUEUED", "RETRY", "RUNNING"]),
                BackgroundJob.available_at <= now,
                or_(BackgroundJob.lease_until.is_(None), BackgroundJob.lease_until < now),
                or_(
                    BackgroundJob.dispatched_at.is_(None),
                    BackgroundJob.dispatched_at < now - timedelta(seconds=60),
                ),
            )
            .order_by(BackgroundJob.available_at)
            .with_for_update(skip_locked=True)
            .limit(50)
        )
    )
    count = 0
    for job in jobs:
        queue = "documents" if job.kind == "DOCUMENT" else "monitoring"
        celery_app.send_task("schemeguard.execute", args=[str(job.id)], queue=queue, task_id=str(uuid4()))
        job.dispatched_at = now
        count += 1
    await session.commit()
    return count


async def claim(
    session: AsyncSession, identifier: UUID, attempts: int, lease_seconds: int
) -> BackgroundJob | None:
    now = datetime.now(UTC)
    job = await session.scalar(select(BackgroundJob).where(BackgroundJob.id == identifier).with_for_update())
    if (
        not job
        or job.status in {"SUCCEEDED", "FAILED"}
        or job.available_at > now
        or (job.lease_until and job.lease_until > now)
    ):
        await session.rollback()
        return None
    if job.attempts >= attempts:
        job.status = "FAILED"
        job.error_code = "attempt_limit"
        job.finished_at = now
        await session.commit()
        return None
    job.status = "RUNNING"
    job.attempts += 1
    job.lease_until = now + timedelta(seconds=lease_seconds)
    await session.commit()
    return job
