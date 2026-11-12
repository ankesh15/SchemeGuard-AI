from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_scheme_service
from app.schemas.error import ErrorResponse
from app.schemas.scheme import SchemeDetail, SchemeFilters, SchemePage, SchemeQuery
from app.services.scheme import SchemeService

router = APIRouter(
    prefix="/schemes",
    tags=["schemes"],
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
Service = Annotated[SchemeService, Depends(get_scheme_service)]


@router.get("", response_model=SchemePage)
async def list_schemes(service: Service, query: Annotated[SchemeQuery, Query()]) -> SchemePage:
    return await service.list(query)


@router.get("/filters", response_model=SchemeFilters)
async def scheme_filters(service: Service) -> SchemeFilters:
    return await service.filters()


@router.get(
    "/{scheme_id}",
    response_model=SchemeDetail,
    responses={404: {"model": ErrorResponse, "description": "Scheme not found"}},
)
async def get_scheme(scheme_id: UUID, service: Service) -> SchemeDetail:
    return await service.get(scheme_id)
