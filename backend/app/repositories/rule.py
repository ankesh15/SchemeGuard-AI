from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.eligibility.expressions import EXPRESSION_ADAPTER
from app.models import DocumentVersion, RuleCondition, RulePublication, RuleSet


class RuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def approved_for(self, scheme_id: UUID, assessed_on: date) -> RuleSet | None:
        candidates = list(
            await self.session.scalars(
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
            )
        )
        if not candidates:
            return None
        if len(candidates) > 1:
            try:
                for condition in candidates[0].conditions:
                    EXPRESSION_ADAPTER.validate_python(condition.expression)
            except ValueError as error:
                raise HTTPException(
                    503, "Approved rule configuration is unavailable for safe evaluation"
                ) from error
            publication = await self.session.scalar(
                select(RulePublication).where(RulePublication.rule_set_id == candidates[0].id)
            )
            if not publication or not {str(item.id) for item in candidates[1:]} <= set(
                publication.replaced_rule_set_ids
            ):
                raise HTTPException(
                    409, "Ambiguous approved policy versions require explicit applicability review"
                )
        return candidates[0]

    async def by_id(self, identifier: UUID) -> RuleSet | None:
        return await self.session.scalar(
            select(RuleSet)
            .where(RuleSet.id == identifier, RuleSet.approval_status == "APPROVED")
            .options(
                selectinload(RuleSet.conditions).selectinload(RuleCondition.evidence),
                selectinload(RuleSet.document).selectinload(DocumentVersion.source),
            )
        )
