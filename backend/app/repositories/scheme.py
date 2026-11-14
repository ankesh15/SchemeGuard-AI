from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import Applicability, IndianState
from app.models import RuleSet, Scheme
from app.schemas.scheme import SchemeFilters, SchemeQuery


class SchemeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def available_rules() -> ColumnElement[bool]:
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        return (Scheme.status != "inactive") & select(RuleSet.id).where(
            RuleSet.scheme_id == Scheme.id,
            RuleSet.approval_status == "APPROVED",
            RuleSet.effective_from <= today,
            or_(RuleSet.effective_to.is_(None), RuleSet.effective_to >= today),
            or_(Scheme.is_demo, RuleSet.approval_basis == "human_review"),
        ).exists()

    async def availability(self, scheme_ids: list[UUID]) -> set[UUID]:
        return set(
            await self.session.scalars(
                select(Scheme.id).where(Scheme.id.in_(scheme_ids), self.available_rules())
            )
        )

    async def filters(self) -> SchemeFilters:
        categories = list(
            await self.session.scalars(select(Scheme.category).distinct().order_by(Scheme.category))
        )
        coverage = await self.session.execute(
            select(Scheme.applicability, Scheme.applicable_states).distinct()
        )
        states: set[str] = set()
        for applicability, verified_states in coverage:
            if applicability == Applicability.NATIONAL:
                states.update(state.value for state in IndianState)
            elif applicability == Applicability.STATES:
                states.update(verified_states or [])
        return SchemeFilters(categories=categories, states=[IndianState(state) for state in sorted(states)])

    async def list(self, query: SchemeQuery) -> tuple[list[Scheme], int]:
        statement = select(Scheme)
        if query.is_demo is not None:
            statement = statement.where(Scheme.is_demo == query.is_demo)
        if query.eligibility_available is not None:
            predicate = self.available_rules()
            statement = statement.where(predicate if query.eligibility_available else ~predicate)
        if query.search is not None:
            # User wildcards are literals, and all values are bound SQL parameters.
            term = query.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    Scheme.name.ilike(pattern, escape="\\"),
                    Scheme.description.ilike(pattern, escape="\\"),
                )
            )
        if query.category is not None:
            statement = statement.where(Scheme.category == query.category)
        if query.state is not None:
            statement = statement.where(
                or_(
                    Scheme.applicability == Applicability.NATIONAL,
                    (Scheme.applicability == Applicability.STATES)
                    & Scheme.applicable_states.contains([query.state.value]),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        rows = await self.session.scalars(
            statement.options(selectinload(Scheme.sources))
            .order_by(Scheme.name, Scheme.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows), total or 0

    async def get(self, scheme_id: UUID) -> Scheme | None:
        return await self.session.scalar(
            select(Scheme).where(Scheme.id == scheme_id).options(selectinload(Scheme.sources))
        )
