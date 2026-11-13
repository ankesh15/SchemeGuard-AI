"""Backup and restore verification; drops only the UUID-named recovery test database it creates."""

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / ".local/backups" / ("phase7-recovery-" + uuid4().hex)
BACKUP.mkdir(mode=0o700, parents=True)
NAME = "sg_recovery_" + uuid4().hex + "_test"
assert NAME.startswith("sg_recovery_") and NAME.endswith("_test")


def compose(*args, input=None, env=None):
    return subprocess.check_output(["docker", "compose", *args], cwd=ROOT, input=input, env=env)


def db(script):
    return compose("exec", "-T", "-e", "RESTORE_DATABASE=" + NAME, "db", "sh", "-ec", script)


snapshot = r"""
import asyncio,json,hashlib
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import make_engine
async def main():
 e=make_engine(get_settings())
 try:
  async with e.connect() as c:
   tables=list(await c.scalars(text("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('public','sg_checkpoints') ORDER BY 1")))
   result={}
   for table in tables:
    rows=sorted(await c.scalars(text(f'SELECT row_to_json(t)::text FROM {table} t')))
    result[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
   print(json.dumps(result,sort_keys=True))
 finally:await e.dispose()
asyncio.run(main())
"""
before = json.loads(compose("exec", "-T", "api", "python", "-c", snapshot))
created = False
try:
    dump = db('pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc')
    path = BACKUP / "database.dump"
    path.write_bytes(dump)
    path.chmod(0o600)
    archive = compose("exec", "-T", "api", "tar", "-C", "/var/lib/schemeguard/documents", "-czf", "-", ".")
    path = BACKUP / "documents.tar.gz"
    path.write_bytes(archive)
    path.chmod(0o600)
    db('createdb -U "$POSTGRES_USER" "$RESTORE_DATABASE"')
    created = True
    compose(
        "exec",
        "-T",
        "-e",
        "RESTORE_DATABASE=" + NAME,
        "db",
        "sh",
        "-ec",
        'pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DATABASE" --no-owner --single-transaction --exit-on-error',
        input=dump,
    )
    restore_code = snapshot.replace(
        "e=make_engine(get_settings())",
        'settings=get_settings(); settings=settings.model_copy(update={"postgres_db":'
        + repr(NAME)
        + ',"database_url":None}); e=make_engine(settings)',
    )
    restored = json.loads(compose("exec", "-T", "api", "python", "-c", restore_code))
    assert before == restored, (
        "Restored metadata differs from source snapshot; retain backup for investigation"
    )
    # Restore only into a fresh temporary directory. Never extract over the live volume.
    validate = r"""
import asyncio,hashlib,io,tarfile,tempfile,json
from pathlib import Path
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import make_engine
from app.ingestion.storage import DocumentStorage
from app.auth.encryption import unseal
import sys
archive=sys.stdin.buffer.read()
async def main():
 settings=get_settings(); e=make_engine(settings)
 try:
  with tempfile.TemporaryDirectory(prefix='sg-recovery-test-') as tmp:
   with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:tar.extractall(tmp,filter='data')
   storage=DocumentStorage(Path(tmp))
   async with e.connect() as c:
    for key,sha,size in await c.execute(text('SELECT v.storage_key,v.content_sha256,v.content_length_bytes FROM document_versions v JOIN document_assets a ON a.document_version_id=v.id')):
     assert len(storage.read(key,sha,settings.pdf_max_bytes))==size
    for owner,payload in await c.execute(text('SELECT user_id,encrypted_data FROM profiles')):unseal(settings,owner,'profile',payload)
   print('PASS: restored original PDFs match preserved checksums; private profiles decrypt with separately retained key')
 finally:await e.dispose()
asyncio.run(main())
"""
    proof = compose("exec", "-T", "api", "python", "-c", validate, input=archive).decode().strip()
    result = {
        "result": "PASS",
        "restored_tables": len(restored),
        "restored_rows": sum(item["count"] for item in restored.values()),
        "database": "UUID-named non-production recovery database",
        "documents": proof,
        "backup_location": str(BACKUP.relative_to(ROOT)),
        "key": "Not included in backup; retained separately in existing private environment",
    }
    (BACKUP / "verification.json").write_text(json.dumps(result, indent=2))
    (BACKUP / "verification.json").chmod(0o600)
    print(json.dumps(result, indent=2))
finally:
    if created:
        db('dropdb -U "$POSTGRES_USER" "$RESTORE_DATABASE"')
