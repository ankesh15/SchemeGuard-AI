"""Recreate this Compose project's services and compare all metadata rows."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot_code = """
import asyncio
import json
import hashlib
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import make_engine

async def main():
    engine = make_engine(get_settings())
    try:
        async with engine.connect() as connection:
            snapshot = {}
            for table in ('schemes', 'scheme_sources', 'document_versions', 'rule_sets', 'rule_conditions', 'rule_evidence', 'users', 'login_sessions', 'rate_limits', 'audit_events', 'source_authorizations', 'document_assets', 'document_pages', 'document_chunks', 'document_processing_jobs', 'extracted_rule_candidates', 'candidate_evidence', 'extraction_errors'):
                rows = sorted(await connection.scalars(text(f'SELECT row_to_json(t)::text FROM {table} t')))
                snapshot[table] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
            assert snapshot['schemes']['count'] >= 5, 'Seed the schemes first'
            from app.ingestion.storage import DocumentStorage
            storage = DocumentStorage(get_settings().document_storage_root)
            async with engine.connect() as blobs_connection:
                originals = await blobs_connection.execute(text('SELECT v.storage_key, v.content_sha256, v.content_length_bytes FROM document_versions v JOIN document_assets a ON a.document_version_id = v.id ORDER BY v.id'))
                snapshot['original_pdf_bytes'] = []
                for key, checksum, size in originals:
                    content = storage.read(key, checksum, get_settings().pdf_max_bytes)
                    assert len(content) == size
                    snapshot['original_pdf_bytes'].append({'key':key, 'sha256':checksum, 'size':size})
            print(json.dumps(snapshot, sort_keys=True))
    finally:
        await engine.dispose()

asyncio.run(main())
"""


def snapshot() -> str:
    return subprocess.check_output(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", snapshot_code],
        cwd=root,
        text=True,
    ).strip()


before = snapshot()
subprocess.run(
    [
        "docker",
        "compose",
        "up",
        "-d",
        "--force-recreate",
        "--wait",
        "--wait-timeout",
        "120",
        "db",
        "api",
        "frontend",
    ],
    cwd=root,
    check=True,
)
assert snapshot() == before, "Metadata changed across container recreation"
print(
    "PASS: all 18 metadata/rule/processing/authentication tables and original PDF checksums persisted after recreating all three containers"
)
