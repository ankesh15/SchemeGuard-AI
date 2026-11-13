from math import ceil
from uuid import UUID

from fastapi import HTTPException

from app.repositories.scheme import SchemeRepository
from app.schemas.scheme import SchemeDetail, SchemeFilters, SchemePage, SchemeQuery, SchemeRead
from app.services.currency import outdated_schemes


class SchemeService:
    def __init__(self, repository: SchemeRepository) -> None:
        self.repository = repository

    async def list(self, query: SchemeQuery) -> SchemePage:
        schemes, total = await self.repository.list(query)
        available = await self.repository.availability([scheme.id for scheme in schemes])
        outdated = await outdated_schemes(self.repository.session, [scheme.id for scheme in schemes])
        return SchemePage(
            items=[
                SchemeRead.model_validate(scheme).model_copy(
                    update={
                        "eligibility_available": scheme.id in available,
                        "policy_currency": "POTENTIALLY_OUTDATED"
                        if scheme.id in outdated
                        else "APPROVED"
                        if scheme.id in available
                        else "UNVERIFIED",
                    }
                )
                for scheme in schemes
            ],
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=ceil(total / query.page_size),
        )

    async def get(self, scheme_id: UUID) -> SchemeDetail:
        scheme = await self.repository.get(scheme_id)
        if scheme is None:
            raise HTTPException(status_code=404, detail="Scheme not found")
        available = await self.repository.availability([scheme.id])
        outdated = await outdated_schemes(self.repository.session, [scheme.id])
        return SchemeDetail.model_validate(scheme).model_copy(
            update={
                "eligibility_available": scheme.id in available,
                "policy_currency": "POTENTIALLY_OUTDATED"
                if scheme.id in outdated
                else "APPROVED"
                if scheme.id in available
                else "UNVERIFIED",
            }
        )

    async def filters(self) -> SchemeFilters:
        return await self.repository.filters()
