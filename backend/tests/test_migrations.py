import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import BACKEND
from tests.support import disposable_database


async def test_migrations_upgrade_downgrade_and_match_models(test_settings):
    async with disposable_database(test_settings.sqlalchemy_url) as url:
        env = os.environ | {"DATABASE_URL": url.render_as_string(hide_password=False)}

        async def alembic(*arguments):
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "alembic", *arguments, cwd=BACKEND, env=env
            )
            assert await process.wait() == 0

        await alembic("upgrade", "head")
        await alembic("upgrade", "head")
        await alembic("check")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                assert (
                    await connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0001_initial_metadata"
                )
                tables = set(
                    await connection.scalars(
                        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    )
                )
                assert {"schemes", "scheme_sources", "document_versions"} <= tables
        finally:
            await engine.dispose()
        await alembic("downgrade", "base")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT to_regclass('public.schemes')")) is None
        finally:
            await engine.dispose()
        await alembic("upgrade", "head")
