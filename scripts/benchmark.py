"""Small sequential local smoke measurements, not a capacity/load benchmark."""

import json
import math
import os
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("SCHEMEGUARD_API_URL", "http://localhost:8000")


def request(path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


supported = request("/api/v1/schemes?eligibility_available=true&page_size=100")
demo = next(item for item in supported["items"] if item["is_demo"])
profile = {
    "age": 21,
    "annual_income_inr": 240000,
    "course": "engineering",
    "study_mode": "full_time",
    "enrollment_date": "2026-08-01",
    "receives_other_scholarship": False,
    "requests_disability_support": False,
}
results = {}
for label, path, body in [
    ("health", "/health", None),
    ("database_readiness", "/ready", None),
    ("scheme_search", "/api/v1/schemes?search=Scholarship&page_size=20", None),
    (
        "deterministic_assessment",
        "/api/v1/eligibility/check",
        {"scheme_id": demo["id"], "synthetic_profile": True, "profile": profile},
    ),
]:
    request(path, body)
    timings = []
    for _ in range(20):
        start = time.perf_counter()
        request(path, body)
        timings.append(1000 * (time.perf_counter() - start))
    results[label] = {
        "samples": 20,
        "p50_ms": round(statistics.median(timings), 3),
        "p95_ms": round(sorted(timings)[math.ceil(0.95 * len(timings)) - 1], 3),
        "max_ms": round(max(timings), 3),
    }
code = r"""
import asyncio,json
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import make_engine
async def main():
 e=make_engine(get_settings())
 try:
  async with e.connect() as c:
   p=await c.scalar(text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT id,name FROM schemes WHERE name ILIKE '%Scholarship%' ORDER BY name,id LIMIT 20"))
   indexes=list(await c.scalars(text("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename IN ('schemes','rule_sets','assessments','notifications','background_jobs') ORDER BY indexname")))
   print(json.dumps({'search_plan':p,'reviewed_indexes':indexes}))
 finally:await e.dispose()
asyncio.run(main())
"""
plans = json.loads(
    subprocess.check_output(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", code], cwd=ROOT, text=True
    )
)
print(
    json.dumps(
        {
            "environment": "local Docker development; sequential HTTP from host; warmup excluded",
            "latency": results,
            "postgresql": plans,
            "limitations": [
                "20 samples per endpoint, one sequential client; not a load/capacity/SLA claim.",
                "PDF/mock-extraction/RAG/monitoring/reassessment measurements are in the isolated A/B/C demonstration output.",
                "Real Gemini/S3/network latency is not measured without configured access.",
            ],
        },
        indent=2,
    )
)
