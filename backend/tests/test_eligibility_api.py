from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.demo_policy import SYNTHETIC_PASS_PROFILE
from app.models import DocumentVersion, RuleCondition, RuleEvidence, RuleSet, Scheme, SchemeSource
from app.repositories.rule import RuleRepository
from app.seed_demo import DEMO_ID, RULE_SET_ID, seed_demo
from tests.conftest import MANIFEST


@pytest_asyncio.fixture
async def demo_rules(session):
    assert await seed_demo(session, MANIFEST.parent)
    return DEMO_ID


async def check(client, scheme_id, profile):
    return await client.post(
        "/api/v1/eligibility/check",
        json={"scheme_id": str(scheme_id), "synthetic_profile": True, "profile": profile},
    )


async def test_requirements_and_pass_report_are_grounded(client, demo_rules, session):
    requirements = await client.get(f"/api/v1/schemes/{demo_rules}/requirements")
    assert requirements.status_code == 200
    body = requirements.json()
    assert body["available"] and body["is_demo"]
    assert body["rule_set"]["version_number"] == 1
    assert body["rule_set"]["approval_basis"] == "synthetic_fixture"
    assert len(body["fields"]) == 8 and len(body["requirements"]) == 6
    before = [
        await session.scalar(select(func.count()).select_from(table))
        for table in (Scheme, RuleSet, DocumentVersion)
    ]
    response = await check(client, demo_rules, SYNTHETIC_PASS_PROFILE)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    report = response.json()
    assert report["result"] == "PASS" and report["assessment"] == "Known conditions satisfied"
    assert report["official_application_url"] is None
    assert report["missing_fields"] == [] and "profile" not in report
    assert all(item["result"] == "PASS" and item["evidence"] for item in report["requirements"])
    assert all(
        item["evidence"][0]["document_sha256"] == report["rule_set"]["source_document_sha256"]
        for item in report["requirements"]
    )
    after = [
        await session.scalar(select(func.count()).select_from(table))
        for table in (Scheme, RuleSet, DocumentVersion)
    ]
    assert before == after


@pytest.mark.parametrize(
    "profile,result,assessment,missing",
    [
        (SYNTHETIC_PASS_PROFILE | {"age": 17}, "FAIL", "Requirements not satisfied", []),
        (
            {},
            "UNKNOWN",
            "More information required",
            [
                "age",
                "annual_income_inr",
                "course",
                "enrollment_date",
                "receives_other_scholarship",
                "requests_disability_support",
                "study_mode",
            ],
        ),
        (
            SYNTHETIC_PASS_PROFILE | {"annual_income_inr": None},
            "UNKNOWN",
            "More information required",
            ["annual_income_inr"],
        ),
        (
            SYNTHETIC_PASS_PROFILE | {"requests_disability_support": True},
            "UNKNOWN",
            "More information required",
            ["disability_percent"],
        ),
    ],
)
async def test_fail_unknown_and_missing_fields(client, demo_rules, profile, result, assessment, missing):
    response = await check(client, demo_rules, profile)
    assert response.status_code == 200
    report = response.json()
    assert report["result"] == result and report["assessment"] == assessment
    assert [item["key"] for item in report["missing_fields"]] == missing


@pytest.mark.parametrize(
    "profile",
    [
        {"age": True},
        {"age": -1},
        {"age": "21.5"},
        {"annual_income_inr": "NaN"},
        {"annual_income_inr": "1e1000000"},
        {"enrollment_date": "2026-02-30"},
        {"course": "unlisted"},
        {"name": "Do not collect names"},
        {"receives_other_scholarship": "false"},
    ],
)
async def test_invalid_profiles_are_422_without_echoing_inputs(client, demo_rules, profile):
    response = await check(client, demo_rules, profile)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "Do not collect names" not in response.text


async def test_no_approved_government_rules_means_unknown(client, session):
    scheme = await session.scalar(select(Scheme).where(Scheme.is_demo.is_(False)).limit(1))
    body = (await client.get(f"/api/v1/schemes/{scheme.id}/requirements")).json()
    assert not body["available"] and body["fields"] == [] and body["rule_set"] is None
    report = (await check(client, scheme.id, {})).json()
    assert report["result"] == "UNKNOWN" and report["reason"] == "NO_APPROVED_RULE_SET"
    assert report["rule_set"] is None and report["trace"] is None
    assert report["official_application_url"] == "https://scholarships.gov.in/Students"


async def test_request_validation_missing_ids_and_cors(client, demo_rules):
    assert (await check(client, uuid4(), {})).status_code == 404
    assert (await client.get("/api/v1/schemes/not-a-uuid/requirements")).status_code == 422
    assert (
        await client.post("/api/v1/eligibility/check", json={"scheme_id": str(demo_rules), "profile": {}})
    ).status_code == 422
    for flag in (False, "true", 1):
        response = await client.post(
            "/api/v1/eligibility/check",
            json={"scheme_id": str(demo_rules), "profile": {}, "synthetic_profile": flag},
        )
        assert response.status_code == 422
    preflight = await client.options(
        "/api/v1/eligibility/check",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert (
        preflight.status_code == 200
        and preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    )


async def test_immutable_rule_content_evidence_and_classification(session, demo_rules):
    for statement in (
        update(RuleSet).where(RuleSet.id == RULE_SET_ID).values(version_number=2),
        update(RuleSet).where(RuleSet.id == RULE_SET_ID).values(approval_status="DRAFT"),
        update(RuleCondition).values(label="Changed"),
        update(RuleEvidence).values(excerpt="Changed"),
        update(Scheme).where(Scheme.id == demo_rules).values(is_demo=False),
        text("DELETE FROM rule_sets"),
        text("TRUNCATE rule_conditions CASCADE"),
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(statement)


async def clone_rule(session, version, effective_from, effective_to=None, approve=False):
    original = await session.get(RuleSet, RULE_SET_ID)
    rule = RuleSet(
        scheme_id=DEMO_ID,
        version_number=version,
        title="Test-only version",
        approval_status="DRAFT",
        effective_from=effective_from,
        effective_to=effective_to,
        source_document_version_id=original.source_document_version_id,
        profile_fields=original.profile_fields,
        scope_note="Test-only policy version",
    )
    session.add(rule)
    await session.flush()
    original_condition = await session.scalar(
        select(RuleCondition)
        .where(RuleCondition.rule_set_id == RULE_SET_ID)
        .order_by(RuleCondition.position)
        .limit(1)
    )
    condition = RuleCondition(
        rule_set_id=rule.id,
        condition_key=original_condition.condition_key,
        label=original_condition.label,
        position=0,
        expression=original_condition.expression,
    )
    session.add(condition)
    await session.flush()
    session.add(
        RuleEvidence(
            rule_set_id=rule.id,
            condition_id=condition.id,
            document_version_id=rule.source_document_version_id,
            locator="Test fixture section 1",
            excerpt="Test-only copy of age condition",
        )
    )
    await session.flush()
    if approve:
        rule.approval_status = "APPROVED"
        rule.approved_at = datetime.now(UTC)
        rule.approved_by = "test-fixture"
        rule.approval_basis = "synthetic_fixture"
        await session.flush()
    return rule


async def test_only_effective_approved_versions_are_selected(session, demo_rules):
    today = date(2026, 11, 12)
    await clone_rule(session, 2, today + timedelta(days=1), approve=True)
    await clone_rule(session, 3, today, approve=False)
    await clone_rule(session, 4, date(2026, 1, 1), date(2026, 1, 31), approve=True)
    repository = RuleRepository(session)
    assert (await repository.approved_for(DEMO_ID, today)).version_number == 1
    assert (await repository.approved_for(DEMO_ID, today + timedelta(days=1))).version_number == 2


async def test_approval_requires_evidence_and_cannot_insert_approved(session, demo_rules):
    original = await session.get(RuleSet, RULE_SET_ID)
    draft = RuleSet(
        scheme_id=DEMO_ID,
        version_number=2,
        title="Incomplete",
        effective_from=date(2026, 1, 1),
        source_document_version_id=original.source_document_version_id,
        profile_fields=original.profile_fields,
        scope_note="Test",
    )
    session.add(draft)
    await session.flush()
    with pytest.raises(IntegrityError, match="evidence"):
        async with session.begin_nested():
            await session.execute(
                update(RuleSet)
                .where(RuleSet.id == draft.id)
                .values(
                    approval_status="APPROVED",
                    approved_at=datetime.now(UTC),
                    approved_by="test",
                    approval_basis="synthetic_fixture",
                )
            )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                RuleSet(
                    scheme_id=DEMO_ID,
                    version_number=3,
                    title="Bypass",
                    approval_status="APPROVED",
                    effective_from=date(2026, 1, 1),
                    source_document_version_id=original.source_document_version_id,
                    profile_fields=[],
                    scope_note="Test",
                    approved_at=datetime.now(UTC),
                    approved_by="test",
                    approval_basis="synthetic_fixture",
                )
            )
            await session.flush()
    with pytest.raises(IntegrityError, match="another scheme"):
        async with session.begin_nested():
            real_id = await session.scalar(select(Scheme.id).where(Scheme.is_demo.is_(False)).limit(1))
            session.add(
                RuleSet(
                    scheme_id=real_id,
                    version_number=1,
                    title="Wrong source",
                    effective_from=date(2026, 1, 1),
                    source_document_version_id=original.source_document_version_id,
                    profile_fields=[],
                    scope_note="Test",
                )
            )
            await session.flush()


async def test_seed_demo_repeatability_and_draft_children_guard(session, demo_rules):
    assert not await seed_demo(session, MANIFEST.parent)
    assert await session.scalar(select(func.count()).select_from(RuleSet)) == 1
    assert await session.scalar(select(func.count()).select_from(RuleEvidence)) == 6
    with pytest.raises(IntegrityError, match="draft"):
        async with session.begin_nested():
            session.add(
                RuleCondition(
                    rule_set_id=RULE_SET_ID, condition_key="later", label="Later", position=9, expression={}
                )
            )
            await session.flush()


async def test_malformed_approved_expression_fails_closed(client, session, demo_rules):
    original = await session.get(RuleSet, RULE_SET_ID)
    rule = RuleSet(
        scheme_id=DEMO_ID,
        version_number=2,
        title="Invalid expression test",
        effective_from=date(2026, 1, 1),
        source_document_version_id=original.source_document_version_id,
        profile_fields=original.profile_fields,
        scope_note="Isolated malformed fixture",
    )
    session.add(rule)
    await session.flush()
    condition = RuleCondition(
        rule_set_id=rule.id,
        condition_key="unsafe",
        label="Invalid expression",
        position=0,
        expression={"kind": "python", "key": "unsafe", "code": "never execute stored code"},
    )
    session.add(condition)
    await session.flush()
    session.add(
        RuleEvidence(
            rule_set_id=rule.id,
            condition_id=condition.id,
            document_version_id=rule.source_document_version_id,
            locator="Test-only reference",
            excerpt="Invalid configuration test",
        )
    )
    await session.flush()
    rule.approval_status = "APPROVED"
    rule.approved_at = datetime.now(UTC)
    rule.approved_by = "test-fixture"
    rule.approval_basis = "synthetic_fixture"
    await session.flush()
    assert (await check(client, demo_rules, SYNTHETIC_PASS_PROFILE)).status_code == 503
    assert (await client.get(f"/api/v1/schemes/{demo_rules}/requirements")).status_code == 503


async def test_synthetic_approval_cannot_publish_government_rules(session, demo_rules):
    real = await session.scalar(select(Scheme).where(Scheme.is_demo.is_(False)).limit(1))
    source = await session.scalar(select(SchemeSource).where(SchemeSource.scheme_id == real.id).limit(1))
    document = DocumentVersion(
        source_id=source.id,
        version_number=1,
        content_sha256="b" * 64,
        content_length_bytes=1,
        media_type="text/plain",
        storage_key="tests/synthetic-guard.txt",
        retrieved_at=datetime.now(UTC),
    )
    session.add(document)
    await session.flush()
    original = await session.get(RuleSet, RULE_SET_ID)
    rule = RuleSet(
        scheme_id=real.id,
        version_number=1,
        title="Isolated approval guard test",
        effective_from=date(2026, 1, 1),
        source_document_version_id=document.id,
        profile_fields=original.profile_fields,
        scope_note="Never published outside this disposable test",
    )
    session.add(rule)
    await session.flush()
    condition = RuleCondition(
        rule_set_id=rule.id, condition_key="guard", label="Test guard", position=0, expression={}
    )
    session.add(condition)
    await session.flush()
    session.add(
        RuleEvidence(
            rule_set_id=rule.id,
            condition_id=condition.id,
            document_version_id=document.id,
            locator="Synthetic test",
            excerpt="Not a government rule",
        )
    )
    await session.flush()
    with pytest.raises(IntegrityError, match="human review"):
        async with session.begin_nested():
            await session.execute(
                update(RuleSet)
                .where(RuleSet.id == rule.id)
                .values(
                    approval_status="APPROVED",
                    approved_at=datetime.now(UTC),
                    approved_by="test-fixture",
                    approval_basis="synthetic_fixture",
                )
            )
