"""Illustrative category assessments in disposable PostgreSQL, never real policy publication."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.assessment.templates import DemonstrationTemplate, templates
from app.eligibility.engine import Result, evaluate
from app.models import (
    Assessment,
    BackgroundJob,
    DocumentVersion,
    Notification,
    PolicyChange,
    RuleCandidate,
    RuleCondition,
    RuleEvidence,
    RuleSet,
    Scheme,
)
from app.seed_demo import DEMO_ID, seed_demo
from tests.conftest import DATA
from tests.test_citizen import citizen_context as citizen_context
from tests.test_citizen import signup
from tests.test_monitoring import setup_monitor
from tests.test_phase4_workflow import workflow_context as workflow_context

CASES = [
    ("scholarship", {"current_student": False}),
    ("agriculture", {"occupation": "other"}),
    ("health", {"has_health_cover": True}),
    ("skills", {"employment_status": "full_time"}),
    ("women_child", {"family_support_type": "other"}),
    ("housing", {"owns_home": True}),
    ("business", {"has_business_plan": False}),
    ("social_welfare", {"requests_support": False}),
    ("pension", {"receives_pension": True}),
]


async def metadata(session, category, **changes):
    item = Scheme(
        slug="isolated-assessment-" + uuid4().hex,
        name="Isolated category test metadata",
        category=category,
        status="listed",
        applicability="unknown",
        applicable_states=None,
        is_demo=False,
    )
    for key, value in changes.items():
        setattr(item, key, value)
    session.add(item)
    await session.flush()
    return item


async def requirements(client, scheme):
    response = await client.get(f"/api/v1/schemes/{scheme.id}/assessment-requirements")
    assert response.status_code == 200, response.text
    return response.json()


async def assess(client, scheme, profile, **extra):
    response = await client.post(
        "/api/v1/assessment/check", json={"scheme_id": str(scheme.id), "profile": profile, **extra}
    )
    return response


@pytest.mark.parametrize("category,fail", CASES)
def test_authored_templates_pass_fail_unknown(category, fail):
    template = templates()[category]
    assert template.basis == "project_authored_illustration"
    assert evaluate(template.program, template.sample_profile).result == Result.PASS
    assert evaluate(template.program, template.sample_profile | fail).result == Result.FAIL
    assert evaluate(template.program, {}).result == Result.UNKNOWN


def test_templates_are_distinct_typed_and_have_no_policy_evidence():
    unique = {template.id: template for template in templates().values()}
    assert len(unique) == 9
    assert "course_level" in {field.key for field in templates()["education"].program.fields}
    assert "course_level" not in {field.key for field in templates()["housing"].program.fields}
    assert "occupation" in {field.key for field in templates()["agriculture"].program.fields}
    assert "annual_family_income_inr" not in {field.key for field in templates()["business"].program.fields}
    data = templates()["education"].model_dump(mode="json")
    for alteration in ["evidence", "invalid_operator", "missing_description"]:
        invalid = deepcopy(data)
        if alteration == "evidence":
            invalid["official_source_url"] = "https://example.invalid/not-evidence"
        elif alteration == "invalid_operator":
            invalid["program"]["expression"]["children"][0]["operator"] = "eval"
        else:
            invalid["criteria_notes"] = {}
        with pytest.raises(ValidationError):
            DemonstrationTemplate.model_validate(invalid)


@pytest.mark.parametrize("age,result", [(15, "FAIL"), (16, "PASS"), (30, "PASS"), (31, "FAIL")])
def test_education_age_boundaries(age, result):
    template = templates()["scholarship"]
    assert evaluate(template.program, template.sample_profile | {"age_years": age}).result == result


@pytest.mark.parametrize("category,fail", CASES)
async def test_category_api_traces_are_not_government_rules(client, session, category, fail):
    scheme = await metadata(session, category)
    info = await requirements(client, scheme)
    assert info["available"] and info["assessment_mode"] == "ILLUSTRATIVE"
    assert not info["is_demo"] and info["rule_set"] is None
    assert all(not item["evidence"] for item in info["requirements"])
    assert info["criteria_token"] == (await requirements(client, scheme))["criteria_token"]
    for profile, expected in [
        (info["sample_profile"], "PASS"),
        (info["sample_profile"] | fail, "FAIL"),
        ({}, "UNKNOWN"),
    ]:
        response = await assess(client, scheme, profile, criteria_token=info["criteria_token"])
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["result"] == expected and report["assessment_mode"] == "ILLUSTRATIVE"
        assert report["template"]["basis"] == "project_authored_illustration"
        assert report["template"]["version"] == 1 and report["rule_set"] is None
        assert report["policy_currency"] == "UNVERIFIED"
        assert response.headers["cache-control"] == "no-store"

        def no_citations(node):
            assert node["evidence"] == []
            for child in node["children"]:
                no_citations(child)

        no_citations(report["trace"])
        if expected == "UNKNOWN":
            assert report["missing_fields"]
            assert report["applicant_details"] == []


async def test_real_catalog_metadata_sources_and_legacy_contracts(client, session):
    await seed_demo(session, DATA)
    public = (await client.get("/api/v1/schemes?is_demo=false&page_size=100")).json()
    assert public["total"] == 5 and all(not item["is_demo"] for item in public["items"])
    assert (await client.get("/api/v1/schemes")).json()["total"] == 6
    selected = public["items"][0]
    assert selected["assessment_mode"] == "ILLUSTRATIVE" and not selected["eligibility_available"]
    # Use ID strings at the public boundary; real IDs and source URLs are not replaced.
    info = (await client.get(f"/api/v1/schemes/{selected['id']}/assessment-requirements")).json()
    report = (
        await client.post(
            "/api/v1/assessment/check", json={"scheme_id": selected["id"], "profile": info["sample_profile"]}
        )
    ).json()
    assert report["official_source_url"] == selected["official_source_url"]
    assert all(not item["evidence"] for item in report["requirements"])
    legacy = await client.post(
        "/api/v1/eligibility/check",
        json={"scheme_id": selected["id"], "synthetic_profile": True, "profile": {}},
    )
    assert legacy.status_code == 200 and legacy.json()["result"] == "UNKNOWN"
    assert legacy.json()["reason"] == "NO_APPROVED_RULE_SET"
    assert not (await client.get(f"/api/v1/schemes/{selected['id']}/requirements")).json()["available"]
    assert (await client.get(f"/api/v1/schemes/{DEMO_ID}/assessment-requirements")).json()[
        "assessment_mode"
    ] == "UNSUPPORTED"
    filtered = (
        await client.get(
            "/api/v1/schemes?is_demo=false&category=scholarship&search=AICTE&state=Assam&page_size=1"
        )
    ).json()
    assert all(not item["is_demo"] and item["category"] == "scholarship" for item in filtered["items"])
    assert (await client.get("/api/v1/schemes?is_demo=false&page=2&page_size=2")).json()["page"] == 2


async def test_state_questions_only_use_verified_catalog_coverage(client, session):
    scoped = await metadata(session, "housing", applicability="states", applicable_states=["Goa"])
    info = await requirements(client, scoped)
    assert "state" in {field["key"] for field in info["fields"]}
    assert info["sample_profile"]["state"] == "Goa"
    assert (await assess(client, scoped, info["sample_profile"])).json()["result"] == "PASS"
    assert (await assess(client, scoped, info["sample_profile"] | {"state": "Assam"})).json()[
        "result"
    ] == "FAIL"
    without_state = {key: value for key, value in info["sample_profile"].items() if key != "state"}
    result = (await assess(client, scoped, without_state)).json()
    assert result["result"] == "UNKNOWN" and result["missing_fields"] == [
        {"key": "state", "label": "State or union territory"}
    ]
    unknown = await metadata(session, "housing")
    assert "state" not in {field["key"] for field in (await requirements(client, unknown))["fields"]}
    assert "state" not in {field.key for field in templates()["housing"].program.fields}


@pytest.mark.parametrize(
    "changes", [{"category": "transport"}, {"category": "housing", "status": "inactive"}]
)
async def test_unsupported_is_explicit_not_a_fabricated_assessment(client, session, changes):
    scheme = await metadata(session, **changes)
    info = await requirements(client, scheme)
    assert info["assessment_mode"] == "UNSUPPORTED" and not info["available"] and info["fields"] == []
    report = (await assess(client, scheme, {})).json()
    assert report["result"] == "UNKNOWN" and report["template"] is None and report["trace"] is None
    assert (await assess(client, scheme, {"age_years": 21})).status_code == 422


@pytest.mark.parametrize(
    "profile",
    [
        {"age_years": True},
        {"age_years": -1},
        {"annual_family_income_inr": "NaN"},
        {"name": "do-not-collect"},
        {"course_level": "unsupported"},
    ],
)
async def test_invalid_and_identifying_details_are_rejected(client, session, profile):
    scheme = await metadata(session, "education")
    response = await assess(client, scheme, profile)
    assert response.status_code == 422 and "do-not-collect" not in response.text


async def test_templates_do_not_write_rules_private_reports_or_monitoring(client, session):
    scheme = await metadata(session, "education")
    models = (
        RuleSet,
        RuleCondition,
        RuleEvidence,
        DocumentVersion,
        RuleCandidate,
        Assessment,
        BackgroundJob,
        PolicyChange,
        Notification,
    )

    async def snapshot():
        return [await session.scalar(select(func.count()).select_from(model)) for model in models]

    before = await snapshot()
    info = await requirements(client, scheme)
    assert (await assess(client, scheme, info["sample_profile"])).json()["result"] == "PASS"
    assert await snapshot() == before
    assert (await assess(client, scheme, {}, criteria_token="f" * 64)).status_code == 409
    response = await client.post(
        "/api/v1/assessment/check",
        json={"scheme_id": str(scheme.id), "profile": {}, "assessment_mode": "APPROVED_POLICY"},
    )
    assert response.status_code == 422
    assert (await client.get("/api/v1/schemes/not-an-id/assessment-requirements")).status_code == 422
    assert (await client.get(f"/api/v1/schemes/{uuid4()}/assessment-requirements")).status_code == 404


async def test_human_approved_policy_precedence_and_evidence(client, session, workflow_context):
    _, _, scheme, document, _, _ = workflow_context
    before = await requirements(client, scheme)
    assert before["assessment_mode"] == "ILLUSTRATIVE"
    await setup_monitor(client, session, workflow_context)
    approved = await requirements(client, scheme)
    assert approved["assessment_mode"] == "APPROVED_POLICY" and approved["template"] is None
    assert approved["rule_set"]["approval_basis"] == "human_review"
    assert {field["key"] for field in approved["fields"]} == {"age_years"}
    assert (await assess(client, scheme, {}, criteria_token=before["criteria_token"])).status_code == 409
    for profile, result in [({"age_years": 18}, "PASS"), ({"age_years": 17}, "FAIL"), ({}, "UNKNOWN")]:
        report = (await assess(client, scheme, profile, criteria_token=approved["criteria_token"])).json()
        assert report["result"] == result and report["assessment_mode"] == "APPROVED_POLICY"
        assert report["rule_set"]["id"] == approved["rule_set"]["id"] and report["template"] is None
        assert report["requirements"][0]["evidence"][0]["document_version_id"] == document["id"]


@pytest.mark.parametrize("status", [409, 503])
async def test_no_fallback_for_an_ambiguous_or_broken_approved_policy(client, session, monkeypatch, status):
    from fastapi import HTTPException

    from app.repositories.rule import RuleRepository

    scheme = await metadata(session, "education")

    async def ambiguous(*args, **kwargs):
        raise HTTPException(status, "Approved policy is not safe to evaluate")

    monkeypatch.setattr(RuleRepository, "approved_for", ambiguous)
    assert (await client.get(f"/api/v1/schemes/{scheme.id}/assessment-requirements")).status_code == status
    assert (await assess(client, scheme, {})).status_code == status


async def test_citizen_save_api_cannot_persist_a_template_as_approved_policy(
    client, session, citizen_context
):
    scheme = await metadata(session, "education")
    info = await requirements(client, scheme)
    assert (await assess(client, scheme, info["sample_profile"])).json()["result"] == "PASS"
    _, headers = await signup(client)
    body = {
        "scheme_id": str(scheme.id),
        "request_key": str(uuid4()),
        "use_saved_profile": False,
        "profile": {},
    }
    denied = await client.post(
        "/api/v1/assessments", headers=headers, json=body | {"assessment_mode": "ILLUSTRATIVE"}
    )
    assert denied.status_code == 422
    saved = await client.post("/api/v1/assessments", headers=headers, json=body)
    assert (
        saved.status_code == 201
        and saved.json()["result"] == "UNKNOWN"
        and saved.json()["rule_set_id"] is None
    )
    detail = (await client.get("/api/v1/assessments/" + saved.json()["id"])).json()
    assert "template" not in detail["report"]
    assert await session.scalar(select(func.count()).select_from(Notification)) == 0
    assert await session.scalar(select(func.count()).select_from(BackgroundJob)) == 0
