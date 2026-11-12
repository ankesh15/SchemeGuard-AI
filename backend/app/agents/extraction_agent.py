"""Reuse Phase 3 processing, with stable IDs for crash-safe extraction."""

from datetime import UTC, datetime, timedelta
from uuid import uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import LLMProvider
from app.auth.security import Administrator
from app.core.config import Settings
from app.models import AgentWorkflow, ProcessingJob, User
from app.services.ingestion import process_document


async def extract_candidates(
    session: AsyncSession, settings: Settings, workflow: AgentWorkflow, provider: LLMProvider
) -> ProcessingJob:
    job = await session.get(ProcessingJob, workflow.extraction_job_id) if workflow.extraction_job_id else None
    if job is None or job.status == "FAILED":
        user = await session.get(User, workflow.requested_by)
        if not user or not user.is_active or user.role != "admin":
            raise ValueError("The workflow initiator must remain an active administrator")
        administrator = Administrator(
            user.id, user.username, datetime.now(UTC) + timedelta(minutes=5), "workflow-internal"
        )
        stable_id = uuid5(workflow.id, f"extraction:{workflow.attempts}")
        job = await process_document(
            session,
            settings,
            administrator,
            workflow.document_version_id,
            "gemini",
            provider,
            job_id=stable_id,
        )
        workflow.extraction_job_id = job.id
        await session.commit()
    if (
        job.document_version_id != workflow.document_version_id
        or job.status not in {"PENDING_REVIEW", "INCOMPLETE"}
        or job.candidate_count < 1
    ):
        raise ValueError("Extraction has no reviewable candidate rules; inspect its processing errors")
    return job
