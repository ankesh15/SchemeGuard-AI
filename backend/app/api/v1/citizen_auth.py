import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.admin_auth import DB, Credentials, SessionRead, login_common
from app.auth.encryption import cipher
from app.auth.security import (
    COOKIE_NAME,
    PASSWORDS,
    Administrator,
    audit,
    digest,
    limit,
    require_citizen,
    require_origin,
    require_user,
    verify_password,
)
from app.models import (
    Assessment,
    CitizenProfile,
    LoginSession,
    Notification,
    NotificationPreference,
    ReassessmentEvent,
    User,
)
from app.schemas.citizen import AccountDelete, AccountPatch, PasswordChange, RegisterRequest

router = APIRouter(tags=["citizen authentication"])
Citizen = Annotated[Administrator, Depends(require_citizen)]
Account = Annotated[Administrator, Depends(require_user)]


@router.post("/auth/register", response_model=SessionRead, status_code=201)
async def register(body: RegisterRequest, request: Request, response: Response, session: DB) -> SessionRead:
    require_origin(request)
    cipher(request.app.state.settings)
    await limit(session, "registration:" + (request.client.host if request.client else "unknown"), 5, 3600)
    if await session.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(409, "Username is unavailable")
    async with request.app.state.password_slots:
        hashed = await asyncio.to_thread(PASSWORDS.hash, body.password.get_secret_value())
    user = User(username=body.username, password_hash=hashed, role="citizen")
    session.add(user)
    try:
        await session.flush()
        session.add(NotificationPreference(user_id=user.id))
        audit(session, "citizen_registered", user.id)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Username is unavailable") from error
    return await login_common(
        Credentials(username=body.username, password=body.password),
        request,
        response,
        session,
        admin_only=False,
    )


@router.post("/auth/login", response_model=SessionRead)
async def login(body: Credentials, request: Request, response: Response, session: DB) -> SessionRead:
    return await login_common(body, request, response, session, admin_only=False)


def clear_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        secure=request.app.state.settings.app_env == "production",
        samesite="strict",
    )


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, user: Account, session: DB) -> None:
    await session.execute(
        update(LoginSession)
        .where(LoginSession.token_hash == digest(request.cookies[COOKIE_NAME]))
        .values(revoked_at=datetime.now(UTC))
    )
    audit(session, "account_logout", user.id)
    await session.commit()
    clear_cookie(request, response)


@router.get("/me")
async def me(user: Account, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "csrf_token": user.csrf_token,
        "expires_at": user.expires_at,
        "password_reset_available": False,
    }


async def verified_password(session: DB, request: Request, user: Administrator, password: str) -> User:
    await limit(session, f"password-action:{user.id}", 10, 900)
    account = await session.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not account or not account.is_active or account.role != "citizen":
        raise HTTPException(401, "Account unavailable")
    async with request.app.state.password_slots:
        valid = await asyncio.to_thread(verify_password, account.password_hash, password)
    if not valid:
        raise HTTPException(401, "Current password is incorrect")
    return account


@router.patch("/me")
async def patch_account(body: AccountPatch, request: Request, user: Citizen, session: DB) -> dict[str, str]:
    account = await verified_password(session, request, user, body.current_password.get_secret_value())
    existing = await session.scalar(select(User.id).where(User.username == body.username, User.id != user.id))
    if existing:
        raise HTTPException(409, "Username is unavailable")
    account.username = body.username
    audit(session, "account_username_changed", user.id)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Username is unavailable") from error
    return {"username": account.username}


@router.post("/auth/password", status_code=204)
async def change_password(
    body: PasswordChange, request: Request, response: Response, user: Citizen, session: DB
) -> None:
    account = await verified_password(session, request, user, body.current_password.get_secret_value())
    async with request.app.state.password_slots:
        account.password_hash = await asyncio.to_thread(PASSWORDS.hash, body.new_password.get_secret_value())
    await session.execute(
        update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=datetime.now(UTC))
    )
    audit(session, "citizen_password_changed", user.id)
    await session.commit()
    clear_cookie(request, response)


@router.delete("/me", status_code=204)
async def delete_account(
    body: AccountDelete, request: Request, response: Response, user: Citizen, session: DB
) -> None:
    if not body.acknowledge_deletion:
        raise HTTPException(422, "Confirm deletion of private profiles, assessments and notifications")
    account = await verified_password(session, request, user, body.current_password.get_secret_value())
    for model in (Notification, ReassessmentEvent):
        await session.execute(delete(model).where(model.user_id == user.id))
    assessments = list(
        await session.scalars(
            select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.created_at.desc())
        )
    )
    while assessments:
        parents = {item.parent_id for item in assessments if item.parent_id}
        leaves = [item for item in assessments if item.id not in parents]
        if not leaves:
            raise HTTPException(409, "Assessment ownership history needs operator reconciliation")
        for item in leaves:
            await session.delete(item)
        await session.flush()
        removed = {item.id for item in leaves}
        assessments = [item for item in assessments if item.id not in removed]
    for private_model in (CitizenProfile, NotificationPreference):
        await session.execute(delete(private_model).where(private_model.user_id == user.id))
    await session.execute(
        update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=datetime.now(UTC))
    )
    account.username = "deleted_" + user.id.hex
    account.password_hash = "disabled"
    account.is_active = False
    audit(session, "citizen_account_deleted", user.id)
    await session.commit()
    clear_cookie(request, response)
