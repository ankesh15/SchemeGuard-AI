from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.scheme import SchemeRepository
from app.services.scheme import SchemeService


def get_scheme_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SchemeService:
    return SchemeService(SchemeRepository(session))
