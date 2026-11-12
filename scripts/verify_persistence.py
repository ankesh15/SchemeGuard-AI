"""Recreate this Compose project's services and compare all metadata rows."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot_code = """
import asyncio
import json
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import make_engine

async def main():
    engine = make_engine(get_settings())
    try:
        async with engine.connect() as connection:
            snapshot = {}
            for table in ('schemes', 'scheme_sources', 'document_versions', 'rule_sets', 'rule_conditions', 'rule_evidence'):
                rows = await connection.scalars(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY id'))
                snapshot[table] = [json.loads(row) for row in rows]
            assert len(snapshot['schemes']) >= 5, 'Seed the schemes first'
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
    "PASS: all six metadata/rule tables persisted after recreating the database, API, and frontend containers"
)
