import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import make_engine
from app.models import BackgroundJob, MonitoringRun, SourceMonitor
from app.services.jobs import claim, dispatch
from app.services.monitoring import monitor_document, schedule_due
from app.workers.celery_app import celery_app

logger = logging.getLogger("schemeguard.worker")


async def dispatch_pending() -> int:
    engine = make_engine(get_settings())
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await schedule_due(session)
            return await dispatch(session)
    finally:
        await engine.dispose()


@celery_app.task(name="schemeguard.dispatch", ignore_result=True)  # type: ignore[untyped-decorator]
def dispatch_task() -> int:
    return asyncio.run(dispatch_pending())


async def execute_job(
    identifier: UUID,
    *,
    settings: Settings | None = None,
    sessions: async_sessionmaker[AsyncSession] | None = None,
) -> str:
    settings = settings or get_settings()
    engine = make_engine(settings)
    factory = sessions or async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as lock_connection:
            key = int.from_bytes(identifier.bytes[:8], "big", signed=True)
            if not await lock_connection.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
                return "DUPLICATE"
            async with factory() as session:
                job = await claim(
                    session, identifier, settings.worker_job_attempts, settings.worker_lease_seconds
                )
                if not job:
                    return "SKIPPED"
                try:
                    if job.kind == "PROBE":
                        result = {"broker": "connected", "database": "connected"}
                    elif job.kind == "MONITOR":
                        result = await monitor_document(session, settings, job)
                    elif job.kind == "DOCUMENT":
                        from app.workers.document_tasks import process_document_job

                        result = await process_document_job(session, settings, job)
                    elif job.kind == "REASSESS":
                        from app.services.reassessment import reassess_change

                        result = await reassess_change(session, settings, UUID(job.payload["change_id"]))
                    elif job.kind == "COMPARE":
                        from app.workers.comparison_tasks import compare_job

                        result = await compare_job(session, job)
                    else:
                        raise ValueError("Unknown durable task kind")
                    job.status = "SUCCEEDED"
                    job.result = result
                    job.finished_at = datetime.now(UTC)
                    job.error_code = None
                except Exception as error:
                    await session.rollback()
                    job = await session.get(BackgroundJob, identifier)
                    assert job is not None
                    code = str(getattr(error, "code", type(error).__name__))[:100]
                    transient = getattr(error, "status", 0) in {502, 503, 504} or isinstance(
                        error, (TimeoutError, ConnectionError, OSError)
                    )
                    job.status = (
                        "RETRY" if transient and job.attempts < settings.worker_job_attempts else "FAILED"
                    )
                    delay = min(30 * 2**job.attempts, 3600)
                    job.available_at = datetime.now(UTC) + timedelta(seconds=delay)
                    job.error_code = code
                    run = await session.scalar(select(MonitoringRun).where(MonitoringRun.job_id == job.id))
                    if run:
                        run.status = "QUEUED" if job.status == "RETRY" else "FAILED"
                        run.error_code = code
                        monitor = await session.get(SourceMonitor, run.monitor_id)
                        if monitor:
                            monitor.last_failure_at = datetime.now(UTC)
                            monitor.verification_status = "POTENTIALLY_OUTDATED"
                            if monitor.last_started_at:
                                job.available_at = max(
                                    job.available_at,
                                    monitor.last_started_at + timedelta(seconds=monitor.min_interval_seconds),
                                )
                    logger.warning(
                        "durable_job_failed",
                        extra={
                            "job_id": str(identifier),
                            "error_type": type(error).__name__,
                            "attempt": job.attempts,
                        },
                    )
                job.lease_until = None
                await session.commit()
                return job.status
    finally:
        await engine.dispose()


@celery_app.task(name="schemeguard.execute", ignore_result=True)  # type: ignore[untyped-decorator]
def execute_task(identifier: str) -> str:
    return asyncio.run(execute_job(UUID(identifier)))
