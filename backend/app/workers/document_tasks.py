from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import BackgroundJob
from app.services.monitoring import process_change_document


async def process_document_job(
    session: AsyncSession, settings: Settings, job: BackgroundJob
) -> dict[str, Any]:
    return await process_change_document(session, settings, job)
