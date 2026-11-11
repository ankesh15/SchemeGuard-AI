from math import ceil
from uuid import UUID

from fastapi import HTTPException

from app.repositories.scheme import SchemeRepository
from app.schemas.scheme import SchemeDetail, SchemePage, SchemeQuery, SchemeRead


class SchemeService:
    def __init__(self, repository: SchemeRepository) -> None:
        self.repository = repository

    async def list(self, query: SchemeQuery) -> SchemePage:
        schemes, total = await self.repository.list(query)
        return SchemePage(
            items=[SchemeRead.model_validate(scheme) for scheme in schemes],
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=ceil(total / query.page_size),
        )

    async def get(self, scheme_id: UUID) -> SchemeDetail:
        scheme = await self.repository.get(scheme_id)
        if scheme is None:
            raise HTTPException(status_code=404, detail="Scheme not found")
        return SchemeDetail.model_validate(scheme)
