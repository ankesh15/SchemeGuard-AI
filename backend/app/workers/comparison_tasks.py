from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob
from app.services.monitoring import compare_change


async def compare_job(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    change = await compare_change(session, UUID(job.payload["change_id"]))
    return {"change_id": str(change.id), "classification": change.classification}
