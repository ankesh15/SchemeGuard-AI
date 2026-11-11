from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import Applicability
from app.models import Scheme
from app.schemas.scheme import SchemeQuery


class SchemeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, query: SchemeQuery) -> tuple[list[Scheme], int]:
        statement = select(Scheme)
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
