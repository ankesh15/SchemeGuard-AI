import asyncio
import os
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import BACKEND
from tests.support import disposable_database


async def test_phase2_upgrade_preserves_phase1_records(test_settings):
    async with disposable_database(test_settings.sqlalchemy_url) as url:
        env = os.environ | {"DATABASE_URL": url.render_as_string(hide_password=False)}

        async def migrate(revision):
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "alembic", "upgrade", revision, cwd=BACKEND, env=env
            )
            assert await process.wait() == 0

        await migrate("0001_initial_metadata")
        scheme_id, source_id, document_id = uuid4(), uuid4(), uuid4()
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO schemes (id, slug, name, category) VALUES (:id, 'migration-fixture', 'Preserve this Phase 1 record', 'scholarship')"
                    ),
                    {"id": scheme_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO scheme_sources (id, scheme_id, url, title, publisher, supported_fields, verification_notes, verified_on) VALUES (:id, :scheme, 'https://example.gov.in/test', 'Synthetic migration source', 'Isolated test fixture', ARRAY['name'], 'Test only', '2026-11-12')"
                    ),
                    {"id": source_id, "scheme": scheme_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO document_versions (id, source_id, version_number, content_sha256, content_length_bytes, media_type, storage_key, retrieved_at) VALUES (:id, :source, 1, :hash, 1, 'text/plain', 'tests/migration.txt', now())"
                    ),
                    {"id": document_id, "source": source_id, "hash": "a" * 64},
                )
                original_created_at = await connection.scalar(
                    text("SELECT created_at FROM schemes WHERE id=:id"), {"id": scheme_id}
                )
        finally:
            await engine.dispose()
        await migrate("head")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text("SELECT name, created_at, is_demo FROM schemes WHERE id=:id"), {"id": scheme_id}
                    )
                ).one()
                assert (
                    row.name == "Preserve this Phase 1 record"
                    and row.created_at == original_created_at
                    and row.is_demo is False
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM scheme_sources WHERE id=:id"), {"id": source_id}
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM document_versions WHERE id=:id"), {"id": document_id}
                    )
                    == 1
                )
        finally:
            await engine.dispose()


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
                    == "0002_eligibility_rules"
                )
                tables = set(
                    await connection.scalars(
                        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    )
                )
                assert {
                    "schemes",
                    "scheme_sources",
                    "document_versions",
                    "rule_sets",
                    "rule_conditions",
                    "rule_evidence",
                } <= tables
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
