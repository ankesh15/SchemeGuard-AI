import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import DocumentVersion, Scheme, SchemeSource
from app.schemas.seed import SeedManifest
from app.seed import load_manifest, seed_schemes
from tests.conftest import MANIFEST


async def test_repeated_seed_preserves_records_and_local_edits(session):
    scheme = await session.scalar(select(Scheme).limit(1))
    await session.execute(
        update(Scheme).where(Scheme.id == scheme.id).values(description="Reviewed local description")
    )
    await session.refresh(scheme)
    before = scheme.updated_at
    manifest = load_manifest(MANIFEST)
    assert await seed_schemes(session, manifest) == {"inserted": 0, "preserved": 5}
    assert await seed_schemes(session, manifest) == {"inserted": 0, "preserved": 5}
    await session.refresh(scheme)
    assert scheme.description == "Reviewed local description"
    assert scheme.updated_at == before
    assert await session.scalar(select(func.count()).select_from(Scheme)) == 5
    assert await session.scalar(select(func.count()).select_from(SchemeSource)) == 11
    assert await session.scalar(select(func.count()).select_from(DocumentVersion)) == 0


async def test_concurrent_seed_is_repeatable(database):
    factory = async_sessionmaker(database)

    async def seed():
        async with factory.begin() as session:
            return await seed_schemes(session, load_manifest(MANIFEST))

    results = await asyncio.gather(seed(), seed())
    assert results == [{"inserted": 0, "preserved": 5}] * 2


@pytest.mark.parametrize(
    "change",
    ["unofficial_source", "no_primary", "unsupported_state", "unknown_with_states", "missing_evidence"],
)
def test_manifest_rejects_unsupported_metadata(change):
    manifest = load_manifest(MANIFEST).model_dump(mode="json")
    scheme = manifest["schemes"][0]
    if change == "unofficial_source":
        scheme["sources"][0]["url"] = "https://untrusted.example/guidelines"
    elif change == "no_primary":
        scheme["sources"][0]["is_primary"] = False
    elif change == "unsupported_state":
        scheme["applicability"] = "states"
        scheme["applicable_states"] = ["Atlantis"]
    elif change == "unknown_with_states":
        scheme["applicable_states"] = ["Assam"]
    elif change == "missing_evidence":
        for source in scheme["sources"]:
            source["supported_fields"] = ["name", "status"]
    with pytest.raises(ValidationError):
        SeedManifest.model_validate(manifest)
