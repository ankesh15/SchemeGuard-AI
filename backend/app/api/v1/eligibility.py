from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import limit
from app.core.database import get_session
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.assessment import AssessmentReport, AssessmentRequest, AssessmentRequirements
from app.schemas.eligibility import EligibilityReport, EligibilityRequest, RequirementsRead
from app.schemas.error import ErrorResponse
from app.services.assessment import AssessmentService
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


@router.get("/schemes/{scheme_id}/assessment-requirements", response_model=AssessmentRequirements)
async def assessment_requirements(
    scheme_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssessmentRequirements:
    response.headers["Cache-Control"] = "no-store"
    return await AssessmentService(SchemeRepository(session), RuleRepository(session)).requirements(scheme_id)


@router.post("/assessment/check", response_model=AssessmentReport)
async def scheme_assessment(
    payload: AssessmentRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssessmentReport:
    response.headers["Cache-Control"] = "no-store"
    address = request.client.host if request.client else "unknown"
    try:
        await limit(session, "public-assessment:" + address, 120, 900)
    except HTTPException as error:
        if error.status_code != 429:
            raise
        raise HTTPException(
            429, "Too many assessment requests; try again later", headers=error.headers
        ) from error
    return await AssessmentService(SchemeRepository(session), RuleRepository(session)).check(payload)
