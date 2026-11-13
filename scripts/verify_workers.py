"""Exercise PostgreSQL outbox -> Beat -> Redis -> worker without external fetches."""
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4
root=Path(__file__).resolve().parents[1]
def execute(code):
    return subprocess.check_output(["docker","compose","exec","-T","api","python","-c",code],cwd=root,text=True).strip()
key="supervised-worker-probe:"+uuid4().hex
code='''import asyncio,json
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import get_settings
from app.core.database import make_engine
from app.services.jobs import enqueue
async def main():
 e=make_engine(get_settings())
 async with async_sessionmaker(e,expire_on_commit=False)() as s:
  identifier=await enqueue(s,"PROBE",KEY,{})
  await s.commit();print(identifier)
 await e.dispose()
asyncio.run(main())'''.replace("KEY",repr(key))
identifier=execute(code)
poll='''import asyncio,json
from uuid import UUID
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import get_settings
from app.core.database import make_engine
from app.models import BackgroundJob
async def main():
 e=make_engine(get_settings())
 async with async_sessionmaker(e,expire_on_commit=False)() as s:
  j=await s.get(BackgroundJob,UUID(IDENTIFIER));print(json.dumps({"id":str(j.id),"status":j.status,"attempts":j.attempts,"result":j.result,"error":j.error_code}))
 await e.dispose()
asyncio.run(main())'''.replace("IDENTIFIER",repr(identifier))
deadline=time.monotonic()+90
while True:
    result=json.loads(execute(poll))
    if result["status"] in {"SUCCEEDED","FAILED"}:break
    if time.monotonic()>deadline:raise SystemExit("Worker probe timed out; inspect scheduler/worker logs")
    time.sleep(2)
assert result["status"]=="SUCCEEDED",result
# Duplicate delivery must leave the durable successful operation untouched.
execute('from app.workers.celery_app import celery_app; celery_app.send_task("schemeguard.execute",args=['+repr(identifier)+'],queue="monitoring"); print("duplicate queued")')
time.sleep(2)
after=json.loads(execute(poll))
assert after["attempts"]==1 and after["status"]=="SUCCEEDED",after
print(json.dumps({"result":"PASS","delivery":"PostgreSQL outbox -> singleton Beat -> Redis -> Celery worker","job":after,"duplicate_delivery":"no second execution"},indent=2))
