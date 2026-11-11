"""Explicit, transactional, insert-only seeding of curated official metadata."""

import asyncio
import logging
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import make_engine
from app.core.logging import configure_logging
from app.models import Scheme, SchemeSource
from app.schemas.seed import SeedManifest

SEED_NAMESPACE = UUID("8ac0bb19-34a9-47e3-a124-188e56d81383")
logger = logging.getLogger("schemeguard.seed")


def load_manifest(path: Path) -> SeedManifest:
    return SeedManifest.model_validate_json(path.read_text(encoding="utf-8"))


async def seed_schemes(session: AsyncSession, manifest: SeedManifest) -> dict[str, int]:
    inserted = 0
    preserved = 0
    # Serialize seed commands so concurrent invocations are repeatable too.
    # The caller owns the transaction and commits only the complete manifest.
    await session.execute(text("SELECT pg_advisory_xact_lock(724199173)"))
    for record in manifest.schemes:
        if await session.scalar(select(Scheme.id).where(Scheme.slug == record.slug)):
            preserved += 1
            continue
        scheme_id = uuid5(SEED_NAMESPACE, record.slug)
        scheme = Scheme(id=scheme_id, **record.model_dump(exclude={"sources"}))
        session.add(scheme)
        await session.flush()
        for source in record.sources:
            session.add(
                SchemeSource(
                    id=uuid5(scheme_id, str(source.url)),
                    scheme_id=scheme_id,
                    verified_on=record.verified_on,
                    **(source.model_dump(exclude={"url"}) | {"url": str(source.url)}),
                )
            )
        inserted += 1
    await session.flush()
    return {"inserted": inserted, "preserved": preserved}


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    manifest = load_manifest(settings.seed_data_path)
    engine = make_engine(settings)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False).begin() as session:
            result = await seed_schemes(session, manifest)
        logger.info("seed_completed inserted=%d preserved=%d", result["inserted"], result["preserved"])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
