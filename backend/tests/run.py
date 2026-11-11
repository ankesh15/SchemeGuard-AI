"""Run from the dev container with `python -m tests.run`."""

import asyncio
import os
import sys

from app.core.config import get_settings
from tests.support import disposable_database


async def main() -> int:
    settings = get_settings()
    async with disposable_database(settings.sqlalchemy_url) as url:
        environment = os.environ | {
            "TEST_DATABASE_URL": url.render_as_string(hide_password=False),
            "DATABASE_URL": url.render_as_string(hide_password=False),
            "APP_ENV": "test",
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", *sys.argv[1:], env=environment
        )
        return await process.wait()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
