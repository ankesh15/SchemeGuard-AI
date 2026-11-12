"""Verify the local authenticated workflow against an already registered demo PDF.

Uses the same-origin Next.js proxy and never prints credentials or session data.
"""

import argparse
import getpass
import hashlib
import http.cookiejar
import json
import urllib.error
import urllib.request
from pathlib import Path

OFFICIAL_URL = "https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials", type=Path, help="Private local JSON with username/password; otherwise prompt"
    )
    parser.add_argument("--username", default="reviewer")
    args = parser.parse_args()
    credentials = (
        json.loads(args.credentials.read_text())
        if args.credentials
        else {"username": args.username, "password": getpass.getpass("Administrator password: ")}
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base = "http://localhost:3000"

    def call(path, payload=None, token=None, raw=False):
        headers = {"Origin": base}
        if token:
            headers["X-CSRF-Token"] = token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode() if payload is not None else None
        with opener.open(
            urllib.request.Request(base + "/api/admin/" + path, data=body, headers=headers), timeout=120
        ) as response:
            data = response.read()
            return data if raw else json.loads(data) if data else None

    try:
        call("documents")
        raise AssertionError("Anonymous administration unexpectedly succeeded")
    except urllib.error.HTTPError as error:
        assert error.code == 401
    login = call("auth/login", credentials)
    token = login["csrf_token"]
    try:
        overview = call("overview")
        document = next(
            item for item in call("documents?page_size=100")["items"] if item["source_url"] == OFFICIAL_URL
        )
        identifier = document["id"]
        original = call(f"documents/{identifier}/original", raw=True)
        assert hashlib.sha256(original).hexdigest() == document["checksum"]
        assert len(original) == document["file_size"] and document["page_count"] == 4
        page = call(f"documents/{identifier}/pages/2")
        assert "40%" in page["text_content"] and page["chunks"]
        detail = call(f"documents/{identifier}")
        job = next(
            item for item in detail["jobs"] if item["provider"] == "fixture" and item["candidate_count"] == 1
        )
        candidates = call(f"extractions/{job['id']}/candidates")["items"]
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["review_status"] == "PENDING" and candidate["validation_status"] == "NEEDS_REVIEW"
        assert candidate["evidence"][0]["page_number"] == 2
        assert candidate["payload"]["extraction_uncertainty"]
        try:
            call(f"documents/{identifier}/extract", {"mode": "parse_only"})
            raise AssertionError("Mutation without CSRF unexpectedly succeeded")
        except urllib.error.HTTPError as error:
            assert error.code == 403
        for route in ("/admin", f"/admin/documents/{identifier}", f"/admin/extractions/{job['id']}"):
            with opener.open(base + route, timeout=120) as response:
                html = response.read().decode()
                assert response.status == 200 and "Document intelligence." in html
        with opener.open(
            "http://localhost:8000/api/v1/schemes/" + document["scheme_id"] + "/requirements"
        ) as response:
            requirements = json.load(response)
            assert requirements["available"] is False and requirements["rule_set"] is None
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "document_id": identifier,
                    "mock_job_id": job["id"],
                    "pending_candidates": len(candidates),
                    "pages": document["page_count"],
                    "sha256": document["checksum"],
                    "gemini_configured": overview["gemini_configured"],
                    "verified": [
                        "anonymous denied",
                        "same-origin sign-in",
                        "CSRF denial",
                        "original checksum",
                        "page/chunk evidence",
                        "pending mock candidate",
                        "protected Next.js pages",
                        "no published government rules",
                    ],
                },
                indent=2,
            )
        )
    finally:
        call("auth/logout", {}, token)


if __name__ == "__main__":
    main()
