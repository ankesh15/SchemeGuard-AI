import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import AuditEvent, LoginSession, RateLimit, User

COOKIE_NAME = "schemeguard_session"
PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# A public dummy hash equalizes the password-check path for unknown usernames.
DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=2$c2NoZW1lZ3VhcmQtZHVtbXk$SC5IXBm1KmkB4hioRcd3JHXdiOR9+a6IBuQ2mKgPVBQ"
)


@dataclass(frozen=True)
class Administrator:
    id: UUID
    username: str
    expires_at: datetime
    csrf_token: str


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hmac.new(token.encode(), b"SchemeGuard csrf v1", hashlib.sha256).hexdigest()


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def audit(
    session: AsyncSession,
    action: str,
    actor: UUID | None,
    target: str | None = None,
    **details: str | int | bool,
) -> None:
    session.add(AuditEvent(action=action, actor_id=actor, target_id=target, details=details))


def require_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.admin_allowed_origins:
        raise HTTPException(403, "An explicitly allowed administrator origin is required")


async def limit(session: AsyncSession, key: str, maximum: int, seconds: int) -> None:
    now = datetime.now(UTC)
    window = now - timedelta(seconds=seconds)
    hashed = digest(key)
    statement = insert(RateLimit).values(key_hash=hashed, window_started_at=now, attempts=1)
    limited = statement.on_conflict_do_update(
        index_elements=[RateLimit.key_hash],
        set_={
            "window_started_at": case(
                (RateLimit.window_started_at < window, now), else_=RateLimit.window_started_at
            ),
            "attempts": case((RateLimit.window_started_at < window, 1), else_=RateLimit.attempts + 1),
        },
    ).returning(RateLimit.attempts)
    attempts = await session.scalar(limited)
    await session.commit()
    if attempts is not None and attempts > maximum:
        raise HTTPException(
            429, "Too many administrator requests; try again later", headers={"Retry-After": str(seconds)}
        )


async def require_admin(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Administrator:
    raw = request.cookies.get(COOKIE_NAME, "")
    if len(raw) < 32 or len(raw) > 200:
        raise HTTPException(401, "Administrator sign-in required")
    row = (
        await session.execute(
            select(User, LoginSession)
            .join(LoginSession, LoginSession.user_id == User.id)
            .where(
                LoginSession.token_hash == digest(raw),
                LoginSession.revoked_at.is_(None),
                LoginSession.expires_at > datetime.now(UTC),
                User.is_active.is_(True),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(401, "Administrator sign-in required")
    user, login = row
    if user.role != "admin":
        raise HTTPException(403, "Administrator role required")
    administrator = Administrator(user.id, user.username, login.expires_at, csrf_token(raw))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), administrator.csrf_token):
            raise HTTPException(403, "Valid CSRF token required")
    # Release read transaction before reading uploads or waiting on extraction.
    await session.commit()
    return administrator
