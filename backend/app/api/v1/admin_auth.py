import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    COOKIE_NAME,
    DUMMY_HASH,
    Administrator,
    audit,
    csrf_token,
    digest,
    limit,
    require_admin,
    require_origin,
    verify_password,
)
from app.core.database import get_session
from app.models import LoginSession, User

router = APIRouter(prefix="/admin/auth", tags=["administrator authentication"])
DB = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[Administrator, Depends(require_admin)]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    password: SecretStr = Field(min_length=1, max_length=1024)


class SessionRead(BaseModel):
    user_id: str
    username: str
    role: str = "admin"
    csrf_token: str
    expires_at: datetime


@router.post("/login", response_model=SessionRead)
async def login(body: Credentials, request: Request, response: Response, session: DB) -> SessionRead:
    require_origin(request)
    settings = request.app.state.settings
    ip = request.client.host if request.client else "unknown"
    await limit(session, "login-ip:" + ip, settings.admin_login_limit, settings.admin_rate_window_seconds)
    await limit(
        session, "login-user:" + body.username, settings.admin_login_limit, settings.admin_rate_window_seconds
    )
    user = await session.scalar(select(User).where(User.username == body.username))
    async with request.app.state.password_slots:
        valid = await asyncio.to_thread(
            verify_password, user.password_hash if user else DUMMY_HASH, body.password.get_secret_value()
        )
    if not valid or user is None or not user.is_active or user.role != "admin":
        audit(session, "admin_login_failed", None)
        await session.commit()
        raise HTTPException(401, "Invalid administrator credentials")
    raw = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(hours=settings.admin_session_hours)
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.token_hash == digest(previous))
            .values(revoked_at=datetime.now(UTC))
        )
    session.add(LoginSession(user_id=user.id, token_hash=digest(raw), expires_at=expires))
    audit(session, "admin_login", user.id)
    result = SessionRead(
        user_id=str(user.id), username=user.username, csrf_token=csrf_token(raw), expires_at=expires
    )
    await session.commit()
    response.set_cookie(
        COOKIE_NAME,
        raw,
        max_age=settings.admin_session_hours * 3600,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/session", response_model=SessionRead)
async def current(administrator: Admin, response: Response) -> SessionRead:
    response.headers["Cache-Control"] = "no-store"
    return SessionRead(
        user_id=str(administrator.id),
        username=administrator.username,
        csrf_token=administrator.csrf_token,
        expires_at=administrator.expires_at,
    )


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, administrator: Admin, session: DB) -> None:
    await session.execute(
        update(LoginSession)
        .where(LoginSession.token_hash == digest(request.cookies[COOKIE_NAME]))
        .values(revoked_at=datetime.now(UTC))
    )
    audit(session, "admin_logout", administrator.id)
    await session.commit()
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        secure=request.app.state.settings.app_env == "production",
        httponly=True,
        samesite="strict",
    )
