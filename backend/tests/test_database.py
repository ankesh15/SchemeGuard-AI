import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import DocumentVersion, Scheme, SchemeSource


def document(source_id, version=1, **overrides):
    """Synthetic test bytes; these are not claimed to be government documents."""
    values = {
        "source_id": source_id,
        "version_number": version,
        "content_sha256": hashlib.sha256(f"fixture-{version}".encode()).hexdigest(),
        "content_length_bytes": 9,
        "media_type": "text/plain",
        "storage_key": f"tests/fixture-{version}.txt",
        "retrieved_at": datetime.now(UTC),
    }
    return DocumentVersion(**(values | overrides))


async def test_relationships_load_and_reject_orphans(session):
    source = await session.scalar(select(SchemeSource).limit(1))
    version = document(source.id)
    session.add(version)
    await session.flush()
    scheme = await session.scalar(
        select(Scheme)
        .where(Scheme.id == source.scheme_id)
        .options(selectinload(Scheme.sources).selectinload(SchemeSource.document_versions))
    )
    assert any(version.id == item.id for source in scheme.sources for item in source.document_versions)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(document(uuid4()))
            await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(delete(Scheme).where(Scheme.id == scheme.id))


async def test_document_version_uniqueness_and_same_source_history(session):
    sources = list(await session.scalars(select(SchemeSource).limit(2)))
    first = document(sources[0].id)
    session.add(first)
    await session.flush()
    second = document(sources[0].id, version=2, supersedes_id=first.id)
    session.add(second)
    await session.flush()
    assert second.supersedes_id == first.id
    for invalid in (
        document(sources[0].id, version=1, content_sha256="a" * 64),
        document(sources[0].id, version=3, content_sha256=first.content_sha256),
        document(sources[1].id, version=2, supersedes_id=first.id),
        document(sources[0].id, version=0),
        document(sources[0].id, version=3, content_sha256="invalid"),
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(invalid)
                await session.flush()


@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
async def test_document_versions_are_immutable_in_postgresql(session, operation):
    source = await session.scalar(select(SchemeSource).limit(1))
    version = document(source.id)
    session.add(version)
    await session.flush()
    statement = {
        "update": update(DocumentVersion)
        .where(DocumentVersion.id == version.id)
        .values(storage_key="tampered"),
        "delete": delete(DocumentVersion).where(DocumentVersion.id == version.id),
        "truncate": text("TRUNCATE document_versions CASCADE"),
    }[operation]
    with pytest.raises(IntegrityError, match="immutable"):
        async with session.begin_nested():
            await session.execute(statement)


async def test_source_constraints_and_scheme_timestamps(session):
    scheme = await session.scalar(select(Scheme).limit(1))
    original_timestamp = scheme.updated_at
    await session.execute(
        update(Scheme).where(Scheme.id == scheme.id).values(description="Temporary test edit")
    )
    await session.refresh(scheme)
    assert scheme.updated_at > original_timestamp
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                update(Scheme)
                .where(Scheme.id == scheme.id)
                .values(applicability="states", applicable_states=None)
            )
    source = await session.scalar(
        select(SchemeSource).where(SchemeSource.scheme_id == scheme.id, SchemeSource.is_primary)
    )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                SchemeSource(
                    scheme_id=scheme.id,
                    url="https://example.gov.in/another",
                    title="Synthetic source",
                    publisher="Test",
                    is_primary=True,
                    supported_fields=["name"],
                    verification_notes="Synthetic fixture",
                    verified_on=source.verified_on,
                )
            )
            await session.flush()
