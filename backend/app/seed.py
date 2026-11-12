"""Offline, transactional, insert-only import of curated official metadata."""

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class SeedCatalog:
    files: tuple[Path, ...]
    manifest: SeedManifest


@dataclass(frozen=True)
class ImportStatistics:
    files: int
    records: int
    inserted: int
    preserved: int
    sources_inserted: int
    validation_only: bool = False


def load_manifest(path: Path) -> SeedManifest:
    """Legacy single-file format remains supported, with no record-count cap."""
    return SeedManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_catalog(path: Path) -> SeedCatalog:
    """Validate the entire directory before opening a database transaction.

    Only direct *.json children are imported, in a deterministic order. No
    network requests or source fetching occurs during validation or import.
    """
    if path.is_dir():
        files = tuple(sorted(path.glob("*.json")))
        if not files:
            raise ValueError(f"No category JSON files found in {path}")
    elif path.is_file():
        files = (path,)
    else:
        raise ValueError(f"Seed path does not exist: {path}")
    records = []
    owners: dict[str, Path] = {}
    identities: dict[str, tuple[str, Path]] = {}
    for file in files:
        try:
            manifest = load_manifest(file)
        except ValueError as error:
            raise ValueError(f"Invalid seed file {file}: {error}") from error
        if path.is_dir() and manifest.category is None:
            raise ValueError(f"Category file must declare category: {file}")
        for record in manifest.schemes:
            if record.slug in owners:
                raise ValueError(f"Duplicate slug {record.slug}: {owners[record.slug]} and {file}")
            # Same exact scheme identity under a new slug is a common curation
            # mistake. Different state variants must use explicit distinct names.
            identity = " ".join(record.name.casefold().split())
            if identity in identities:
                other_slug, other_file = identities[identity]
                raise ValueError(f"Duplicate scheme name {record.name}: {other_slug} in {other_file} and {file}")
            owners[record.slug] = file
            identities[identity] = (record.slug, file)
            records.append(record)
    return SeedCatalog(
        files=files,
        manifest=SeedManifest(
            schema_version=1,
            review_method="Validated aggregation of curated category manifests; see each source's verification notes.",
            schemes=records,
        ),
    )


async def seed_schemes(session: AsyncSession, manifest: SeedManifest) -> dict[str, int]:
    """The caller owns commit/rollback; existing rows and sources are untouched."""
    await session.execute(text("SELECT pg_advisory_xact_lock(724199173)"))
    slugs = [record.slug for record in manifest.schemes]
    existing: set[str] = set()
    # Bounded query batches support catalogs larger than driver parameter limits.
    for offset in range(0, len(slugs), 1000):
        existing.update(await session.scalars(select(Scheme.slug).where(Scheme.slug.in_(slugs[offset:offset + 1000]))))
    inserted = 0
    for record in manifest.schemes:
        if record.slug in existing:
            continue
        scheme_id = uuid5(SEED_NAMESPACE, record.slug)
        session.add(Scheme(id=scheme_id, **record.model_dump(exclude={"sources"})))
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
    return {"inserted": inserted, "preserved": len(existing)}


async def seed_catalog(session: AsyncSession, catalog: SeedCatalog) -> ImportStatistics:
    # The same transaction-level lock is reentrant and protects these counts.
    await session.execute(text("SELECT pg_advisory_xact_lock(724199173)"))
    existing = set(await session.scalars(select(Scheme.slug)))
    source_count = sum(len(record.sources) for record in catalog.manifest.schemes if record.slug not in existing)
    result = await seed_schemes(session, catalog.manifest)
    return ImportStatistics(
        files=len(catalog.files), records=len(catalog.manifest.schemes),
        sources_inserted=source_count, **result,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Category directory or legacy manifest; defaults to SEED_DATA_PATH")
    parser.add_argument("--validate-only", action="store_true", help="Validate all records without connecting to PostgreSQL")
    arguments = parser.parse_args()
    # Validation-only requires no secrets or database credentials.
    path = arguments.path or (Path(__import__("os").getenv("SEED_DATA_PATH", "/app/data/schemes")))
    catalog = load_catalog(path)
    if arguments.validate_only:
        print(json.dumps(asdict(ImportStatistics(len(catalog.files), len(catalog.manifest.schemes), 0, 0, 0, True))))
        return
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False).begin() as session:
            statistics = await seed_catalog(session, catalog)
        # Emit counts only after a successful commit. Errors result in non-zero exit.
        logger.info("seed_completed %s", json.dumps(asdict(statistics), sort_keys=True))
        print(json.dumps(asdict(statistics), sort_keys=True))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
