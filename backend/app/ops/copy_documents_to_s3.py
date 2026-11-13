"""Operator-only local-to-S3 migration; defaults to dry-run. Does not change database history."""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.database import make_engine
from app.ingestion.storage import DocumentStorage, S3DocumentStorage
from app.models import DocumentAsset, DocumentVersion


async def copy(execute: bool) -> int:
    settings = get_settings()
    if not settings.s3_bucket:
        raise ValueError("Configure the authorized S3 bucket first")
    engine = make_engine(settings)
    count = 0
    try:
        async with async_sessionmaker(engine)() as session:
            records = await session.scalars(
                select(DocumentVersion).join(
                    DocumentAsset, DocumentAsset.document_version_id == DocumentVersion.id
                )
            )
            for document in records:
                content = await asyncio.to_thread(
                    DocumentStorage(settings.document_storage_root).read,
                    document.storage_key,
                    document.content_sha256,
                    settings.pdf_max_bytes,
                )
                if execute:
                    store = S3DocumentStorage(settings)
                    key, sha = await asyncio.to_thread(store.put, document.source_id, content)
                    assert key == document.storage_key and sha == document.content_sha256
                    assert await asyncio.to_thread(store.read, key, sha, settings.pdf_max_bytes) == content
                count += 1
    finally:
        await engine.dispose()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--copy", action="store_true", help="Write originals to the explicitly configured authorized bucket"
    )
    args = parser.parse_args()
    print(
        f"{'Copied and verified' if args.copy else 'Dry run verified local originals'}: {asyncio.run(copy(args.copy))}"
    )


if __name__ == "__main__":
    main()
