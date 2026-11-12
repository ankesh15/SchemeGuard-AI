"""Live Phase 2 smoke checks. Sends authored synthetic profiles only."""

import hashlib
import json
import os
import urllib.request
from typing import Any

API = os.getenv("SCHEMEGUARD_API_URL", "http://localhost:8000").rstrip("/")
FRONTEND = os.getenv("SCHEMEGUARD_FRONTEND_URL", "http://localhost:3000").rstrip("/")


def request_json(path: str, payload: dict[str, Any] | None = None) -> tuple[Any, Any]:
    request = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        assert response.status == 200
        return json.load(response), response.headers


assert request_json("/health")[0]["status"] == "ok"
assert request_json("/ready")[0]["database"] == "ok"
schemes, _ = request_json("/api/v1/schemes?page_size=100")
demo = next(scheme for scheme in schemes["items"] if scheme["is_demo"])
real = next(scheme for scheme in schemes["items"] if not scheme["is_demo"])
requirements, _ = request_json(f"/api/v1/schemes/{demo['id']}/requirements")
assert requirements["available"] and requirements["rule_set"]["approval_status"] == "APPROVED"
profile = {
    "age": 21,
    "annual_income_inr": "240000",
    "course": "engineering",
    "study_mode": "full_time",
    "enrollment_date": "2026-08-01",
    "receives_other_scholarship": False,
    "requests_disability_support": False,
}
for values, expected in (
    (profile, "PASS"),
    (profile | {"age": 17}, "FAIL"),
    (profile | {"annual_income_inr": None}, "UNKNOWN"),
    (profile | {"requests_disability_support": True}, "UNKNOWN"),
):
    report, headers = request_json(
        "/api/v1/eligibility/check",
        {"scheme_id": demo["id"], "synthetic_profile": True, "profile": values},
    )
    assert report["result"] == expected
    assert headers["Cache-Control"] == "no-store" and headers["X-Request-ID"]
    assert report["rule_set"]["version_number"] == 1
    assert report["official_application_url"] is None
    assert all(item["evidence"] for item in report["requirements"])
    assert "profile" not in report
    print(f"PASS: live synthetic assessment -> {expected}")

unavailable, _ = request_json(f"/api/v1/schemes/{real['id']}/requirements")
assert not unavailable["available"]
unknown, _ = request_json(
    "/api/v1/eligibility/check", {"scheme_id": real["id"], "synthetic_profile": True, "profile": {}}
)
assert unknown["result"] == "UNKNOWN" and unknown["reason"] == "NO_APPROVED_RULE_SET"
preflight = urllib.request.Request(
    API + "/api/v1/eligibility/check",
    method="OPTIONS",
    headers={
        "Origin": FRONTEND,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    },
)
with urllib.request.urlopen(preflight, timeout=10) as response:
    assert response.headers["Access-Control-Allow-Origin"] == FRONTEND

for path, expected_text in (
    ("/", "Clarity before"),
    ("/schemes", "Find a place to start"),
    (f"/schemes/{demo['id']}", "About this scholarship"),
    ("/eligibility", "A synthetic profile"),
    ("/eligibility/report", "Your next explanation starts here"),
):
    with urllib.request.urlopen(FRONTEND + path, timeout=30) as response:
        assert response.status == 200 and expected_text in response.read().decode()
with urllib.request.urlopen(FRONTEND + "/policies/demo-policy-v1.md", timeout=10) as response:
    assert hashlib.sha256(response.read()).hexdigest() == requirements["rule_set"]["source_document_sha256"]
print(
    "PASS: five frontend pages, server-to-API connectivity, CORS, source hash, and unapproved-government-rule fallback"
)
