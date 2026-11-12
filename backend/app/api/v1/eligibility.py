from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.eligibility import EligibilityReport, EligibilityRequest, RequirementsRead
from app.schemas.error import ErrorResponse
from app.services.eligibility import EligibilityService

router = APIRouter(
    tags=["eligibility"],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)


def get_eligibility_service(session: Annotated[AsyncSession, Depends(get_session)]) -> EligibilityService:
    return EligibilityService(SchemeRepository(session), RuleRepository(session))


@router.post("/eligibility/check", response_model=EligibilityReport)
async def check_eligibility(
    payload: EligibilityRequest,
    response: Response,
    service: Annotated[EligibilityService, Depends(get_eligibility_service)],
) -> EligibilityReport:
    response.headers["Cache-Control"] = "no-store"
    return await service.check(payload)


@router.get("/schemes/{scheme_id}/requirements", response_model=RequirementsRead)
async def get_requirements(
    scheme_id: UUID,
    response: Response,
    service: Annotated[EligibilityService, Depends(get_eligibility_service)],
) -> RequirementsRead:
    response.headers["Cache-Control"] = "no-store"
    return await service.requirements(scheme_id)
