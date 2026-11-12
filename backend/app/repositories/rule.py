from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DocumentVersion, RuleCondition, RuleSet


class RuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def approved_for(self, scheme_id: UUID, assessed_on: date) -> RuleSet | None:
        return await self.session.scalar(
            select(RuleSet)
            .where(
                RuleSet.scheme_id == scheme_id,
                RuleSet.approval_status == "APPROVED",
                RuleSet.effective_from <= assessed_on,
                or_(RuleSet.effective_to.is_(None), RuleSet.effective_to >= assessed_on),
            )
            .options(
                selectinload(RuleSet.conditions).selectinload(RuleCondition.evidence),
                selectinload(RuleSet.document).selectinload(DocumentVersion.source),
            )
            .order_by(RuleSet.version_number.desc())
            .limit(1)
        )
