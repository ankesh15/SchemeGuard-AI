from uuid import UUID, uuid4

import pytest


async def test_scheme_listing(client):
    response = await client.get("/api/v1/schemes")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["pages"] == 1
    assert len(body["items"]) == 5
    assert all(item["category"] == "scholarship" for item in body["items"])
    assert all(item["status"] == "listed" for item in body["items"])
    assert all(item["official_source_url"].startswith("https://") for item in body["items"])
    assert all(item["verified_on"] == "2026-11-11" for item in body["items"])
    for item in body["items"]:
        UUID(item["id"])
        assert "eligibility" not in item


async def test_scheme_detail_contains_grounding(client):
    item = (await client.get("/api/v1/schemes", params={"search": "Pragati"})).json()["items"][0]
    response = await client.get(f"/api/v1/schemes/{item['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item["id"]
    assert len(body["sources"]) == 2
    assert sum(source["is_primary"] for source in body["sources"]) == 1
    assert body["applicability"] == "unknown"
    assert body["applicable_states"] is None


async def test_missing_and_invalid_ids(client):
    assert (await client.get(f"/api/v1/schemes/{uuid4()}")).status_code == 404
    response = await client.get("/api/v1/schemes/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["request_id"] == response.headers["x-request-id"]


async def test_pagination_is_stable_and_complete(client):
    pages = [
        (await client.get("/api/v1/schemes", params={"page": page, "page_size": 2})).json()
        for page in (1, 2, 3)
    ]
    assert [len(page["items"]) for page in pages] == [2, 2, 1]
    ids = [item["id"] for page in pages for item in page["items"]]
    assert len(set(ids)) == 5
    assert all(page["total"] == 5 and page["pages"] == 3 for page in pages)
    assert (await client.get("/api/v1/schemes", params={"page": 100})).json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": 100001},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
        {"state": "Atlantis"},
        {"search": " "},
        {"search": "x" * 201},
        {"category": "bad category"},
        {"surprise": "x"},
    ],
)
async def test_invalid_query_parameters(client, params):
    assert (await client.get("/api/v1/schemes", params=params)).status_code == 422


@pytest.mark.parametrize(
    "term,expected",
    [("pRaGaTi", 1), ("undergraduate", 1), ("%", 0), ("_", 0), ("' OR 1=1 --", 0), ("does-not-exist", 0)],
)
async def test_search_is_case_insensitive_and_treats_wildcards_literally(client, term, expected):
    response = await client.get("/api/v1/schemes", params={"search": term})
    assert response.status_code == 200
    assert response.json()["total"] == expected


async def test_category_and_verified_state_filtering(client):
    assert (await client.get("/api/v1/schemes", params={"category": "SCHOLARSHIP"})).json()["total"] == 5
    assert (await client.get("/api/v1/schemes", params={"category": "housing"})).json()["total"] == 0
    for state in ("Assam", " arunachal pradesh ", "Tripura"):
        page = (
            await client.get("/api/v1/schemes", params={"state": state, "category": "scholarship"})
        ).json()
        assert page["total"] == 1
        assert page["items"][0]["slug"] == "ugc-ishan-uday"
    # Unknown coverage is not silently treated as national coverage.
    assert (await client.get("/api/v1/schemes", params={"state": "Maharashtra"})).json()["total"] == 0
    assert (await client.get("/api/v1/schemes", params={"state": "Assam", "search": "Pragati"})).json()[
        "total"
    ] == 0


async def test_openapi_contract(client):
    schema = (await client.get("/openapi.json")).json()
    assert {"/health", "/ready", "/api/v1/schemes", "/api/v1/schemes/{scheme_id}"} <= schema["paths"].keys()
    assert schema["components"]["schemas"]["SchemePage"]["properties"]["items"]["type"] == "array"
