"""Offline curation validation and PostgreSQL import/discovery regressions."""

import json
from uuid import uuid5

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import Scheme, SchemeSource
from app.schemas.seed import SeedManifest
from app.seed import SEED_NAMESPACE, load_catalog, load_manifest, seed_catalog, seed_schemes
from app.seed_demo import seed_demo
from tests.conftest import DATA, MANIFEST

CATALOG = DATA / "schemes"


def fixture_record(index=0, category="scholarship"):
    record = load_manifest(MANIFEST).schemes[0].model_dump(mode="json")
    record.update(
        slug=f"synthetic-capacity-{index}", name=f"Synthetic capacity fixture {index}", category=category
    )
    return record


def write_manifest(path, records, category="scholarship"):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_method": "Isolated synthetic test fixture only",
                "category": category,
                "schemes": records,
            }
        )
    )


def test_curated_catalog_has_unique_traceable_metadata():
    catalog = load_catalog(CATALOG)
    assert 250 <= len(catalog.manifest.schemes) <= 300
    assert len(catalog.files) > 1
    for file in catalog.files:
        manifest = load_manifest(file)
        assert file.stem == manifest.category
        assert all(record.category == manifest.category for record in manifest.schemes)
    by_slug = {record.slug: record for record in catalog.manifest.schemes}
    for original in load_manifest(MANIFEST).schemes:
        assert by_slug[original.slug] == original
    assert len({record.name.casefold() for record in catalog.manifest.schemes}) == len(by_slug)
    assert all(record.sources and record.verified_on for record in by_slug.values())


def test_capacity_has_no_five_or_three_hundred_limit():
    manifest = SeedManifest.model_validate(
        {
            "schema_version": 1,
            "review_method": "Synthetic validation capacity test",
            "schemes": [fixture_record(i) for i in range(501)],
        }
    )
    assert len(manifest.schemes) == 501


@pytest.mark.parametrize(
    "change", ["category_mismatch", "missing_field", "invalid_json", "duplicate_slug", "missing_category"]
)
def test_category_validation_is_atomic_before_database(tmp_path, change):
    file = tmp_path / "scholarship.json"
    write_manifest(file, [fixture_record()])
    data = json.loads(file.read_text())
    if change == "category_mismatch":
        data["schemes"][0]["category"] = "housing"
    elif change == "missing_field":
        del data["schemes"][0]["sources"]
    elif change == "missing_category":
        del data["category"]
    elif change == "duplicate_slug":
        data["schemes"].append(data["schemes"][0])
    file.write_text("not JSON" if change == "invalid_json" else json.dumps(data))
    with pytest.raises(ValueError, match="Invalid seed file|declare category"):
        load_catalog(tmp_path)


@pytest.mark.parametrize("duplicate", ["slug", "name"])
def test_cross_file_duplicates_include_file_names(tmp_path, duplicate):
    first, second = fixture_record(1), fixture_record(2)
    second[duplicate] = first[duplicate]
    write_manifest(tmp_path / "one.json", [first])
    write_manifest(tmp_path / "two.json", [second])
    with pytest.raises(ValueError, match="Duplicate") as error:
        load_catalog(tmp_path)
    assert "one.json" in str(error.value) and "two.json" in str(error.value)


def test_empty_or_missing_directory_rejected(tmp_path):
    with pytest.raises(ValueError, match="No category JSON"):
        load_catalog(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        load_catalog(tmp_path / "missing")


@pytest.mark.parametrize(
    "url",
    [
        "http://dbtbharat.gov.in/central-scheme/list",
        "https://dbtbharat.gov.in.attacker.test/list",
        "https://user:secret@dbtbharat.gov.in/list",
        "https://dbtbharat.gov.in:8443/list",
        "https://example.invalid/fixture",
        "javascript:alert(1)",
    ],
)
def test_invalid_source_urls_rejected(url):
    record = fixture_record()
    record["sources"][0]["url"] = url
    with pytest.raises(ValidationError):
        SeedManifest.model_validate({"schema_version": 1, "review_method": "Test", "schemes": [record]})


async def snapshot(session):
    return {
        table: {
            str(row["id"]): row
            for row in (await session.execute(text(f"SELECT row_to_json(t) FROM {table} t"))).scalars()
        }
        for table in (
            "schemes",
            "scheme_sources",
            "document_versions",
            "rule_sets",
            "rule_conditions",
            "rule_evidence",
        )
    }


async def test_full_import_preserves_ids_sources_approved_rules_and_history(session):
    await seed_demo(session, DATA)
    before = await snapshot(session)
    catalog = load_catalog(CATALOG)
    result = await seed_catalog(session, catalog)
    count = len(catalog.manifest.schemes)
    assert (result.records, result.files, result.inserted, result.preserved) == (
        count,
        len(catalog.files),
        count - 5,
        5,
    )
    assert result.sources_inserted == sum(
        len(record.sources)
        for record in catalog.manifest.schemes
        if record.slug not in {item.slug for item in load_manifest(MANIFEST).schemes}
    )
    after = await snapshot(session)
    for table, rows in before.items():
        assert all(after[table][key] == row for key, row in rows.items())
    again = await seed_catalog(session, catalog)
    assert (again.inserted, again.preserved, again.sources_inserted) == (0, count, 0)
    assert await snapshot(session) == after
    assert await session.scalar(select(func.count()).select_from(Scheme)) == count + 1
    assert (
        await session.scalar(select(func.count()).select_from(SchemeSource))
        == sum(len(record.sources) for record in catalog.manifest.schemes) + 1
    )


async def test_three_hundred_record_postgres_capacity(session):
    records = [fixture_record(i) for i in range(300)]
    manifest = SeedManifest.model_validate(
        {
            "schema_version": 1,
            "review_method": "Synthetic isolated PostgreSQL capacity test",
            "schemes": records,
        }
    )
    assert await seed_schemes(session, manifest) == {"inserted": 300, "preserved": 0}
    assert await seed_schemes(session, manifest) == {"inserted": 0, "preserved": 300}
    assert await session.scalar(select(func.count()).select_from(Scheme)) == 305


async def test_database_failure_rolls_back_entire_multi_file_import(database, tmp_path):
    # Force a late PK conflict without altering the schema or existing data.
    first, second = fixture_record(700), fixture_record(701)
    write_manifest(tmp_path / "one.json", [first])
    write_manifest(tmp_path / "two.json", [second])
    catalog = load_catalog(tmp_path)
    factory = async_sessionmaker(database)
    conflict_id = uuid5(SEED_NAMESPACE, second["slug"])
    async with factory.begin() as session:
        session.add(
            Scheme(
                id=conflict_id,
                slug="synthetic-conflict-local",
                name="Synthetic rollback conflict",
                category="test",
            )
        )
    try:
        with pytest.raises(IntegrityError):
            async with factory.begin() as session:
                await seed_catalog(session, catalog)
        async with factory() as session:
            assert await session.scalar(select(Scheme.id).where(Scheme.slug == first["slug"])) is None
            assert await session.scalar(select(Scheme.id).where(Scheme.slug == second["slug"])) is None
            assert await session.get(Scheme, conflict_id) is not None
            assert await session.scalar(select(func.count()).select_from(SchemeSource)) == 11
    finally:
        async with factory.begin() as session:
            await session.execute(text("DELETE FROM schemes WHERE id=:id"), {"id": conflict_id})


async def test_expanded_api_pagination_filters_details_and_unsupported_eligibility(session, client):
    catalog = load_catalog(CATALOG)
    await seed_catalog(session, catalog)
    total = len(catalog.manifest.schemes)
    seen = []
    for page in range(1, (total + 99) // 100 + 1):
        response = await client.get("/api/v1/schemes", params={"page_size": 100, "page": page})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == total
        seen.extend(item["id"] for item in body["items"])
        assert all(
            item["official_source_url"].startswith("https://") and not item["eligibility_available"]
            for item in body["items"]
        )
    assert len(set(seen)) == total
    filters = (await client.get("/api/v1/schemes/filters")).json()
    assert "agriculture" in filters["categories"] and "Goa" in filters["states"]
    for category in filters["categories"]:
        page = (await client.get("/api/v1/schemes", params={"category": category})).json()
        assert page["total"] == sum(record.category == category for record in catalog.manifest.schemes)
        assert all(item["category"] == category for item in page["items"])
    goa = (await client.get("/api/v1/schemes", params={"state": "Goa", "page_size": 100})).json()
    assert goa["total"] > 5
    assert all("Goa" in item["applicable_states"] for item in goa["items"])
    result = (await client.get("/api/v1/schemes", params={"search": "PM KISAN"})).json()
    item = next(item for item in result["items"] if item["slug"] == "pm-kisan")
    detail = (await client.get(f"/api/v1/schemes/{item['id']}")).json()
    assert detail["sources"][0]["verification_notes"]
    requirements = (await client.get(f"/api/v1/schemes/{item['id']}/requirements")).json()
    assert not requirements["available"] and requirements["fields"] == []
    assert requirements["official_application_url"] is None
    report = (
        await client.post(
            "/api/v1/eligibility/check",
            json={"scheme_id": item["id"], "synthetic_profile": True, "profile": {"age": 20}},
        )
    ).json()
    assert report["result"] == "UNKNOWN" and report["reason"] == "NO_APPROVED_RULE_SET"
    assert report["requirements"] == [] and report["rule_set"] is None
    assert report["official_application_url"] is None
    assert (await client.get("/api/v1/schemes?eligibility_available=true")).json()["total"] == 0
    await seed_demo(session, DATA)
    available = (await client.get("/api/v1/schemes?eligibility_available=true")).json()
    assert available["total"] == 1 and available["items"][0]["is_demo"]
    assert available["items"][0]["eligibility_available"]
    assert (await client.get("/api/v1/schemes?eligibility_available=false")).json()["total"] == total
