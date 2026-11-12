"""Read-only live verification of the curated catalog, API, and Next.js routes."""

import json
import math
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("SCHEMEGUARD_API_URL", "http://localhost:8000").rstrip("/")
FRONTEND = os.getenv("SCHEMEGUARD_FRONTEND_URL", "http://localhost:3000").rstrip("/")


def get(path: str) -> Any:
    with urllib.request.urlopen(API + path, timeout=20) as response:
        assert response.status == 200
        return json.load(response)


def verify() -> None:
    curated = {
        record["slug"]: record
        for file in sorted((ROOT / "data/schemes").glob("*.json"))
        for record in json.loads(file.read_text())["schemes"]
    }
    first = get("/api/v1/schemes?page_size=100")
    items = list(first["items"])
    for number in range(2, first["pages"] + 1):
        items.extend(get(f"/api/v1/schemes?page_size=100&page={number}")["items"])
    assert len({item["id"] for item in items}) == len(items) == first["total"]
    by_slug = {item["slug"]: item for item in items}
    assert curated.keys() <= by_slug.keys()
    assert all(not by_slug[slug]["is_demo"] for slug in curated)
    filters = get("/api/v1/schemes/filters")
    assert {record["category"] for record in curated.values()} <= set(filters["categories"])
    assert "Goa" in filters["states"] and "Assam" in filters["states"]
    for category in filters["categories"]:
        result = get("/api/v1/schemes?" + urllib.parse.urlencode({"category": category}))
        assert all(item["category"] == category for item in result["items"])
    state = get("/api/v1/schemes?state=Goa&page_size=100")
    assert state["total"] >= 53 and all("Goa" in item["applicable_states"] for item in state["items"])
    assert any(item["slug"] == "pm-kisan" for item in get("/api/v1/schemes?search=PM%20KISAN")["items"])
    assert get("/api/v1/schemes?page=100000")["items"] == []

    # Inspect every public source relationship, not just the first page.
    for slug in curated:
        item = by_slug[slug]
        detail = get(f"/api/v1/schemes/{item['id']}")
        primary = [source for source in detail["sources"] if source["is_primary"]]
        assert len(primary) == 1 and primary[0]["url"] == item["official_source_url"]
        assert all(source["verified_on"] and source["verification_notes"] for source in detail["sources"])
    available = get("/api/v1/schemes?eligibility_available=true&page_size=100")
    assert all(item["eligibility_available"] for item in available["items"])
    assert any(item["is_demo"] for item in available["items"])
    # A late alphabetic record used to fail because the questionnaire only loaded
    # the first 100 schemes. Exercise its direct URL through Next.js server fetch.
    unsupported = next(item for item in reversed(items) if not item["eligibility_available"])
    requirements = get(f"/api/v1/schemes/{unsupported['id']}/requirements")
    assert not requirements["available"] and requirements["fields"] == []
    for path, expected in (
        ("/schemes", "Browse government scheme records"),
        (f"/schemes/{unsupported['id']}", "Rules are awaiting verified review"),
        (f"/eligibility?scheme={unsupported['id']}", "More verified information is needed"),
        ("/eligibility", "A synthetic profile"),
    ):
        with urllib.request.urlopen(FRONTEND + path, timeout=30) as response:
            body = response.read().decode()
            assert response.status == 200 and expected in body
            if "?scheme=" in path:
                assert "See my assessment" not in body
    print(
        f"PASS: {len(curated)} curated government records, {len(items)} total database records, {len(filters['categories'])} categories, {math.ceil(len(items) / 6)} explorer pages"
    )
    print(
        "PASS: every source relationship, search/category/state filters, approved-rule flags, metadata-only direct links beyond page one, and frontend-to-API connectivity"
    )


if __name__ == "__main__":
    verify()
