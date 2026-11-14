from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.citizen_auth import Citizen
from app.auth.security import limit
from app.core.database import get_session
from app.core.enums import IndianState
from app.models import Scheme
from app.schemas.citizen import ProfileData
from app.schemas.recommendations import RecommendationOptions, RecommendationPage, RecommendationRequest
from app.services.citizen import get_profile
from app.services.recommendations import INTEREST_GROUPS, RecommendationService

router = APIRouter(tags=["recommendations"])
DB = Annotated[AsyncSession, Depends(get_session)]


@router.get("/recommendations/options")
async def options(session: DB) -> dict[str, Any]:
    categories = sorted(
        set(
            await session.scalars(
                select(Scheme.category).where(Scheme.is_demo.is_(False), Scheme.status != "inactive")
            )
        )
    )
    grouped = {category for _, members in INTEREST_GROUPS.values() for category in members}
    interests = [
        {"value": key, "label": label}
        for key, (label, members) in INTEREST_GROUPS.items()
        if set(members) & set(categories)
    ]
    interests += [
        {"value": category, "label": category.replace("_", " ").title()}
        for category in categories
        if category not in grouped
    ]
    return {
        "categories": categories,
        "interests": interests,
        "states": [state.value for state in IndianState],
    }


@router.post("/recommendations", response_model=RecommendationPage)
async def recommend(
    body: RecommendationRequest, request: Request, response: Response, session: DB
) -> RecommendationPage:
    response.headers["Cache-Control"] = "no-store"
    address = request.client.host if request.client else "unknown"
    try:
        await limit(session, "public-recommendations:" + address, 120, 900)
    except HTTPException as error:
        if error.status_code != 429:
            raise
        raise HTTPException(
            429, "Too many recommendation requests; try again later", headers=error.headers
        ) from error
    profile = ProfileData.model_validate(body.model_dump(include=set(ProfileData.model_fields)))
    query = RecommendationOptions.model_validate(
        body.model_dump(include=set(RecommendationOptions.model_fields))
    )
    return await RecommendationService(session).recommend(profile, query)


@router.post("/me/recommendations", response_model=RecommendationPage)
async def saved_recommendations(
    body: RecommendationOptions, request: Request, response: Response, user: Citizen, session: DB
) -> RecommendationPage:
    response.headers["Cache-Control"] = "no-store"
    await limit(session, f"citizen-recommendations:{user.id}", 120, 900)
    profile = await get_profile(session, request.app.state.settings, user.id)
    return await RecommendationService(session).recommend(profile or ProfileData(), body)
