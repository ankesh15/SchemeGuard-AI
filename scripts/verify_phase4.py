"""Supervised local official-document demo; never approve government rules.

Requires the previously registered Phase 3 official Saksham PDF and its explicitly
mocked extraction. Uses the same-origin Next proxy and keeps credentials private.
"""

import argparse
import getpass
import hashlib
import http.cookiejar
import json
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID, uuid5

OFFICIAL_URL = "https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf"
OFFICIAL_SHA = "06ebed9e50a47ae76cba985ddde78cd65f19f2193b0e4c9c164fff529580474c"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--username", default="reviewer")
    args = parser.parse_args()
    credentials = (
        json.loads(args.credentials.read_text())
        if args.credentials
        else {"username": args.username, "password": getpass.getpass("Administrator password: ")}
    )
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = "http://localhost:3000"

    def admin(path, payload=None, token=None, raw=False):
        headers = {"Origin": base}
        if token:
            headers["X-CSRF-Token"] = token
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        with opener.open(
            urllib.request.Request(base + "/api/admin/" + path, data=body, headers=headers), timeout=330
        ) as response:
            content = response.read()
            return content if raw else json.loads(content) if content else None

    login = admin("auth/login", credentials)
    token = login["csrf_token"]
    try:
        documents = admin("documents?page_size=100")["items"]
        document = next(
            item
            for item in documents
            if item["source_url"] == OFFICIAL_URL and item["checksum"] == OFFICIAL_SHA
        )
        identifier = document["id"]
        original = admin(f"documents/{identifier}/original", raw=True)
        assert hashlib.sha256(original).hexdigest() == OFFICIAL_SHA
        detail = admin(f"documents/{identifier}")
        job = next(
            item for item in detail["jobs"] if item["provider"] == "fixture" and item["candidate_count"] == 1
        )
        key = uuid5(UUID(identifier), "phase4-supervised-official-pending-demo-v1")
        workflow = admin(
            "workflows",
            {"document_version_id": identifier, "extraction_job_id": job["id"], "request_key": str(key)},
            token,
        )
        workflow = admin(
            f"workflows/{workflow['id']}/resume",
            {
                "notes": "Supervised checkpoint recovery verification; keep official policy pending actual human review."
            },
            token,
        )
        assert workflow["status"] == "PENDING_REVIEW", workflow
        review = admin(f"reviews/{workflow['review_id']}")
        assert review["decision"] is None and not review["validation"]["publishable"]
        assert review["workflow"]["published_rule_set_id"] is None
        assert review["draft"]["conditions"][0]["evidence"][0]["page_number"] == 2
        page = admin(f"documents/{identifier}/pages/2")
        assert "40%" in page["text_content"]
        for route in (
            "/admin/workflows",
            "/admin/reviews",
            f"/admin/workflows/{workflow['id']}",
            f"/admin/reviews/{review['id']}",
        ):
            with opener.open(base + route, timeout=120) as response:
                assert response.status == 200 and "Document intelligence." in response.read().decode()
        request = urllib.request.Request(
            "http://localhost:8000/api/v1/eligibility/explain",
            data=json.dumps(
                {
                    "scheme_id": document["scheme_id"],
                    "synthetic_profile": True,
                    "profile": {"disability_percent": 40},
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            assessment = json.load(response)
        assert (
            assessment["report"]["result"] == "UNKNOWN"
            and assessment["report"]["reason"] == "NO_APPROVED_RULE_SET"
        )
        assert not assessment["explanation"]["citations"]
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "scheme_id": document["scheme_id"],
                    "document_id": identifier,
                    "sha256": OFFICIAL_SHA,
                    "pages": document["page_count"],
                    "workflow_id": workflow["id"],
                    "review_id": review["id"],
                    "status": workflow["status"],
                    "provider": workflow["provider"],
                    "synthetic_assessment": assessment["report"]["result"],
                    "human_approval": False,
                    "review_url": base + "/admin/reviews/" + review["id"],
                    "limitations": [
                        "Historical 2020 guideline; current applicability unverified",
                        "Reused explicit mock extraction; live Gemini not exercised",
                        "Incomplete policy remains pending actual human review",
                        "Full publication and vector path tested with simulated review in disposable PostgreSQL",
                    ],
                },
                indent=2,
            )
        )
    finally:
        admin("auth/logout", {}, token)


if __name__ == "__main__":
    main()
