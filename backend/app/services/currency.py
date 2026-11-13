from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SchemeSource, SourceMonitor


async def outdated_schemes(session: AsyncSession, identifiers: list[UUID]) -> set[UUID]:
    if not identifiers:
        return set()
    return set(
        await session.scalars(
            select(SchemeSource.scheme_id)
            .join(SourceMonitor, SourceMonitor.source_id == SchemeSource.id)
            .where(
                SchemeSource.scheme_id.in_(identifiers),
                SourceMonitor.verification_status == "POTENTIALLY_OUTDATED",
            )
        )
    )
