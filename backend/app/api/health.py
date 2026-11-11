import asyncio

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.schemas.error import ErrorResponse
from app.schemas.scheme import HealthRead, ReadyRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health() -> HealthRead:
    return HealthRead()


@router.get(
    "/ready",
    response_model=ReadyRead,
    responses={503: {"model": ErrorResponse, "description": "Database unavailable"}},
)
async def ready(request: Request) -> ReadyRead:
    async with asyncio.timeout(request.app.state.settings.database_timeout_seconds):
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    return ReadyRead()
