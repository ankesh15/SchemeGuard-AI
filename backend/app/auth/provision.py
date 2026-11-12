"""CLI-only admin provisioning. Passwords never appear in command arguments."""

import argparse
import asyncio
import getpass
import re
import sys
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.security import PASSWORDS, audit
from app.core.config import get_settings
from app.core.database import make_engine
from app.models import LoginSession, User


async def provision(username: str, password: str, reset: bool = False) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,79}", username) or not 12 <= len(password) <= 1024:
        raise ValueError("Use a valid lowercase username and a password of 12–1024 characters")
    hashed = await asyncio.to_thread(PASSWORDS.hash, password)
    engine = make_engine(get_settings())
    try:
        async with async_sessionmaker(engine).begin() as session:
            user = await session.scalar(select(User).where(User.username == username).with_for_update())
            if user and not reset:
                raise ValueError("Account exists; use --reset-password explicitly to rotate its password")
            if user:
                if user.role != "admin":
                    raise ValueError("An existing non-admin account cannot be promoted by this command")
                user.password_hash = hashed
                await session.execute(
                    update(LoginSession)
                    .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
                    .values(revoked_at=datetime.now(UTC))
                )
            else:
                user = User(username=username, password_hash=hashed, role="admin")
                session.add(user)
                await session.flush()
            audit(session, "admin_password_reset" if reset else "admin_provisioned", user.id, str(user.id))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()
    secret = (
        sys.stdin.readline().rstrip("\r\n")
        if args.password_stdin
        else getpass.getpass("New administrator password: ")
    )
    asyncio.run(provision(args.username, secret, args.reset_password))
    print("Administrator provisioned; no password or session token is printed.")
