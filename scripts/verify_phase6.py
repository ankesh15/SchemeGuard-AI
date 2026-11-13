"""Verify the real same-origin citizen flow using synthetic data only."""

import http.cookiejar
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = os.getenv("SCHEMEGUARD_FRONTEND_URL", "http://localhost:3000").rstrip("/")
API = os.getenv("SCHEMEGUARD_API_URL", "http://localhost:8000").rstrip("/")
PRIVATE = ROOT / ".local" / "phase6-demo-credentials.json"


def verify() -> None:
    PRIVATE.parent.mkdir(exist_ok=True)
    if PRIVATE.exists():
        credentials = json.loads(PRIVATE.read_text())
    else:
        credentials = {
            "username": "synthetic_demo_" + uuid4().hex[:12],
            "password": secrets.token_urlsafe(32),
        }
        descriptor = os.open(PRIVATE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(credentials, stream)
    client = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    csrf: str | None = None

    def request(
        path: str, body: Any = None, method: str = "GET", status: int = 200
    ) -> Any:
        headers = {"Origin": FRONTEND, "Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        req = urllib.request.Request(
            FRONTEND + "/api/account/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = client.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code == status:
                return None
            raise
        assert response.status == status, (path, response.status)
        assert "no-store" in response.headers.get("Cache-Control", "")
        return json.load(response) if response.status != 204 else None

    try:
        account = request("auth/login", credentials, "POST")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        account = request("auth/register", credentials, "POST", 201)
    csrf = account["csrf_token"]
    assert account["role"] == "citizen"
    profile = {
        "state": "Assam",
        "age_years": 21,
        "annual_family_income_inr": 240000,
        "current_student": True,
        "attributes": {
            "course": "engineering",
            "study_mode": "full_time",
            "enrollment_date": "2026-08-01",
            "receives_other_scholarship": False,
            "requests_disability_support": False,
        },
    }
    assert request("profiles/me", profile, "PUT")["exists"]
    with urllib.request.urlopen(
        API + "/api/v1/schemes?eligibility_available=true&page_size=100", timeout=15
    ) as response:
        demo = next(item for item in json.load(response)["items"] if item["is_demo"])
    saved = request(
        "assessments",
        {
            "scheme_id": demo["id"],
            "request_key": str(uuid4()),
            "allow_reassessment": True,
        },
        "POST",
        201,
    )
    assert saved["result"] == "PASS"
    assert request("assessments/" + saved["id"])["rule_set_id"] == saved["rule_set_id"]
    assert request("assessments/" + saved["id"] + "/reproduce", {}, "POST")["matches_original"]
    assert request("dashboard")["assessment_count"] >= 1
    assert request("notifications")["total"] == 0
    request("auth/logout", {}, "POST", 204)
    request("me", status=401)
    print(json.dumps({
        "result": "PASS",
        "flow": "Next.js cookie proxy -> FastAPI auth -> encrypted profile -> deterministic saved assessment -> historical replay -> logout",
        "synthetic_assessment_id": saved["id"],
        "result_label": saved["assessment"],
        "rule_version": saved["rule_version"],
        "credentials": "Preserved only in ignored .local/phase6-demo-credentials.json (0600); never printed.",
    }, indent=2))


if __name__ == "__main__":
    verify()
