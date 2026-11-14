"""Real PostgreSQL matching and encrypted-profile tests; no real policy publication."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Assessment, CitizenProfile, DocumentVersion, Notification, RuleSet, Scheme, User
from app.schemas.citizen import ProfileData
from app.schemas.recommendations import RecommendationOptions
from app.services.recommendations import RecommendationService
from tests.test_citizen import citizen_context as citizen_context
from tests.test_citizen import signup
from tests.test_monitoring import setup_monitor
from tests.test_phase4_workflow import workflow_context as workflow_context
from tests.test_scheme_assessment import metadata


async def recommend(client, **body):
    response = await client.post("/api/v1/recommendations", json=body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


@pytest.mark.parametrize(
    "profile,category",
    [
        ({"current_student": True}, "scholarship"),
        ({"occupation": "student"}, "scholarship"),
        ({"interests": ["agriculture"]}, "agriculture"),
        ({"interests": ["employment"]}, "skills"),
        ({"occupation": "unemployed"}, "skills"),
        ({"occupation": "self_employed"}, "business"),
        ({"employment_status": "unemployed"}, "skills"),
    ],
)
async def test_profile_signals(client, session, profile, category):
    item = await metadata(session, category)
    data = await recommend(client, **profile)
    match = next(row for row in data["items"] if row["id"] == str(item.id))
    assert match["matching_reasons"] and not match["eligibility_available"]
    assert match["missing_information"]


async def test_unknown_coverage_retained_known_mismatch_excluded(client, session):
    unknown = await metadata(session, "agriculture")
    assam = await metadata(session, "agriculture", applicability="states", applicable_states=["Assam"])
    bihar = await metadata(session, "agriculture", applicability="states", applicable_states=["Bihar"])
    data = await recommend(client, state="Assam", interests=["agriculture"])
    ids = [row["id"] for row in data["items"]]
    assert str(unknown.id) in ids and str(assam.id) in ids and str(bihar.id) not in ids
    assert ids.index(str(assam.id)) < ids.index(str(unknown.id))
    assert (
        "coverage has not been verified"
        in next(row for row in data["items"] if row["id"] == str(unknown.id))["missing_information"][0]
    )


async def test_multiple_interests_dedup_ranking_and_pagination(client, session):
    agri = await metadata(session, "agriculture")
    await metadata(session, "skills")
    body = {
        "interests": ["education", "scholarship", "education", "agriculture", "employment"],
        "current_student": True,
    }
    data = await recommend(client, **body, page_size=30)
    ids = [row["id"] for row in data["items"]]
    assert str(agri.id) in ids and len(ids) == len(set(ids)) == data["total"]
    points = [row["ranking_points"] for row in data["items"]]
    assert points == sorted(points, reverse=True)
    for row in data["items"]:
        assert row["ranking_points"] == sum(row["ranking_factors"].values())
    first = await recommend(client, **body, page_size=2)
    second = await recommend(client, **body, page_size=2, page=2)
    assert first["items"] + second["items"] == data["items"][:4]
    filtered = await recommend(client, **body, category="agriculture")
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == str(agri.id)
    assert not (await recommend(client, **body, page=100))["items"]
    names = await recommend(client, **body, sort_by="name")
    assert [row["name"].casefold() for row in names["items"]] == sorted(
        row["name"].casefold() for row in names["items"]
    )


async def test_income_age_not_used_without_approved_rules(client):
    low = await recommend(client, current_student=True, age_years=12, annual_family_income_inr=0)
    high = await recommend(client, current_student=True, age_years=100, annual_family_income_inr=1e9)
    missing = await recommend(client, current_student=True)
    assert low == high == missing
    assert all(
        row["assessment_mode"] == "ILLUSTRATIVE" and row["approved_rule_version"] is None
        for row in low["items"]
    )
    assert all("approved_conditions" not in row["ranking_factors"] for row in low["items"])


@pytest.mark.parametrize(
    "body", [{}, {"age_years": 21}, {"course_level": "undergraduate"}, {"interests": ["unlisted_category"]}]
)
async def test_no_unrelated_results_for_insufficient_or_unmatched_inputs(client, body):
    data = await recommend(client, **body)
    assert data["total"] == 0 and not data["items"]


@pytest.mark.parametrize(
    "body",
    [
        {"age_years": -1},
        {"age_years": True},
        {"annual_family_income_inr": -1},
        {"interests": ["x"] * 25},
        {"interests": ["<script>"]},
        {"occupation": "unsupported"},
        {"page": 0},
        {"page_size": 301},
        {"sort_by": "income"},
        {"user_id": str(uuid4())},
        {"field_of_study": "x" * 81},
    ],
)
async def test_bounded_validated_inputs(client, body):
    response = await client.post("/api/v1/recommendations", json=body)
    assert response.status_code == 422


async def test_catalog_options_and_source_links(client):
    data = (await client.get("/api/v1/recommendations/options")).json()
    assert data["categories"] == ["scholarship"]
    assert {"value": "education", "label": "Scholarships and Education"} in data["interests"]
    assert "Assam" in data["states"]
    rows = (await recommend(client, interests=["scholarship"]))["items"]
    assert all(row["official_source_url"].startswith("https://") for row in rows)


async def test_guest_no_profile_or_history_persistence(client, session):
    models = [CitizenProfile, Assessment, Notification, DocumentVersion, RuleSet, User, Scheme]
    before = [await session.scalar(select(func.count()).select_from(model)) for model in models]
    body = {"state": "Assam", "annual_family_income_inr": 234567, "interests": ["education"]}
    await recommend(client, **body)
    assert before == [await session.scalar(select(func.count()).select_from(model)) for model in models]


async def test_saved_profile_owner_csrf_and_dashboard_parity(client, session, citizen_context):
    assert (await client.post("/api/v1/me/recommendations", json={})).status_code == 401
    a, headers_a = await signup(client)
    body_a = {
        "current_student": True,
        "interests": ["education"],
        "employment_status": "part_time",
        "field_of_study": "Engineering",
    }
    assert (await client.put("/api/v1/profiles/me", headers=headers_a, json=body_a)).status_code == 200
    encrypted = await session.get(CitizenProfile, UUID(a["user_id"]))
    assert "Engineering" not in encrypted.encrypted_data
    assert (await client.post("/api/v1/me/recommendations", json={})).status_code == 403
    own = await client.post("/api/v1/me/recommendations", headers=headers_a, json={})
    assert own.status_code == 200 and own.json()["total"] > 0
    assert (await client.get("/api/v1/dashboard")).json()["relevant_schemes"] == own.json()["items"][:3]
    _, headers_b = await signup(client)
    assert not (await client.post("/api/v1/me/recommendations", headers=headers_b, json={})).json()["items"]
    assert (
        await client.post("/api/v1/me/recommendations", headers=headers_b, json={"user_id": a["user_id"]})
    ).status_code == 422
    # Updating an older payload remains valid; existing private schema is backward-compatible.
    assert (
        await client.put("/api/v1/profiles/me", headers=headers_b, json={"state": "Bihar"})
    ).status_code == 200


async def test_approved_rule_precedence_and_missing_information(client, session, workflow_context):
    await setup_monitor(client, session, workflow_context)
    scheme = workflow_context[2]
    scheme.category = "scholarship"
    await session.flush()
    partial = await RecommendationService(session).recommend(
        ProfileData(current_student=True), RecommendationOptions()
    )
    row = next(item for item in partial.items if item.id == scheme.id)
    assert row.assessment_mode == "APPROVED_POLICY" and row.approved_rule_version == 1
    assert (
        row.missing_information
        and "Scheme-specific verified eligibility conditions" not in row.missing_information
    )
    assert "approved_assessment" in row.ranking_factors


async def test_approved_conditions_can_match_without_category_guessing(client, session, workflow_context):
    await setup_monitor(client, session, workflow_context)
    scheme = workflow_context[2]
    # This isolated human-reviewed fixture has only an age condition. It is never live policy data.
    rows = await RecommendationService(session).recommend(ProfileData(age_years=21), RecommendationOptions())
    match = next(row for row in rows.items if row.id == scheme.id)
    assert match.approved_rule_version == 1 and match.ranking_factors["approved_conditions"] == 12
    assert not (await RecommendationService(session).recommend(ProfileData(), RecommendationOptions())).items


@pytest.mark.parametrize("value,expected", [("undergraduate", True), ("secondary", False), (None, False)])
def test_education_matching_requires_a_positive_typed_condition(value, expected):
    from app.eligibility.expressions import Exclusion, Program
    from app.services.recommendations import reviewed_education_matches

    program = Program.model_validate(
        {
            "fields": [
                {"key": "course_level", "label": "Education", "value_type": "string", "section": "Education"}
            ],
            "expression": {
                "kind": "comparison",
                "key": "course",
                "field": "course_level",
                "operator": "IN",
                "value_type": "string",
                "value": ["undergraduate"],
            },
        }
    )
    assert reviewed_education_matches(program, {"course_level": value}) is expected
    # A comparison inside an exclusion is not an independently positive education signal.
    excluded = program.model_copy(
        update={"expression": Exclusion(kind="exclude", key="exclude_course", expression=program.expression)}
    )
    assert reviewed_education_matches(excluded, {"course_level": value}) is False
