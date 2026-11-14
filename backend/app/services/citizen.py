"""Owner-scoped private profiles and reproducible deterministic assessments."""

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.encryption import seal, unseal
from app.auth.security import audit
from app.core.config import Settings
from app.models import Assessment, CitizenProfile, NotificationPreference, User
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.citizen import AssessmentCreate, ProfileData
from app.schemas.eligibility import EligibilityReport, EvaluationInput
from app.services.eligibility import EligibilityService


async def active_owner(session: AsyncSession, user_id: UUID) -> User:
    account = await session.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not account or not account.is_active or account.role != "citizen":
        raise HTTPException(401, "Citizen account is unavailable")
    return account


def profile_values(data: ProfileData) -> dict[str, Any]:
    result = {
        key: value
        for key, value in data.model_dump(
            mode="json", exclude={"attributes", "interests", "field_of_study"}, exclude_none=True
        ).items()
    }
    result.update(data.attributes)
    # Explicit compatibility aliases for the authored Phase 2 fixture only.
    if data.age_years is not None:
        result.setdefault("age", data.age_years)
    if data.annual_family_income_inr is not None:
        result.setdefault("annual_income_inr", data.annual_family_income_inr)
    return result


async def get_profile(session: AsyncSession, settings: Settings, user_id: UUID) -> ProfileData | None:
    row = await session.get(CitizenProfile, user_id)
    return (
        ProfileData.model_validate(unseal(settings, user_id, "profile", row.encrypted_data)) if row else None
    )


async def profile_read(session: AsyncSession, settings: Settings, user_id: UUID) -> dict[str, Any]:
    data = await get_profile(session, settings, user_id)
    row = await session.get(CitizenProfile, user_id)
    fields = ["state", "age_years", "annual_family_income_inr", "course_level", "current_student"]
    completed = sum(getattr(data, key) is not None for key in fields) if data else 0
    return {
        "exists": data is not None,
        "profile": data.model_dump(mode="json") if data else ProfileData().model_dump(mode="json"),
        "completeness": {
            "completed": completed,
            "total": len(fields),
            "percent": round(100 * completed / len(fields)),
        },
        "updated_at": row.updated_at if row else None,
        "notice": "Completeness describes these optional profile fields, not eligibility or document verification.",
    }


async def put_profile(
    session: AsyncSession, settings: Settings, user_id: UUID, data: ProfileData
) -> dict[str, Any]:
    await active_owner(session, user_id)
    encrypted = seal(settings, user_id, "profile", data.model_dump(mode="json"))
    row = await session.get(CitizenProfile, user_id)
    if row:
        row.encrypted_data = encrypted
        row.updated_at = datetime.now(UTC)
    else:
        session.add(CitizenProfile(user_id=user_id, encrypted_data=encrypted))
    audit(session, "citizen_profile_updated", user_id)
    await session.commit()
    return await profile_read(session, settings, user_id)


async def preference(session: AsyncSession, user_id: UUID) -> NotificationPreference:
    row = await session.get(NotificationPreference, user_id)
    if row is None:
        row = NotificationPreference(
            user_id=user_id, in_app=True, automatic_reassessment=True, policy_updates=True
        )
        session.add(row)
        await session.flush()
    return row


def private_notices(report: EligibilityReport) -> EligibilityReport:
    notices = [item for item in report.notices if not item.startswith("Synthetic development profiles only.")]
    notices.append(
        "This private saved assessment uses only the fields needed by its pinned rule version. It is not official government approval."
    )
    return report.model_copy(update={"notices": notices})


async def evaluate_private(
    session: AsyncSession, settings: Settings, user_id: UUID, body: AssessmentCreate
) -> tuple[EligibilityReport, dict[str, Any]]:
    data = await get_profile(session, settings, user_id) if body.use_saved_profile else None
    values = profile_values(data) if data else {}
    values.update(body.profile)
    service = EligibilityService(SchemeRepository(session), RuleRepository(session), body.assessed_on)
    _, rule, program = await service.load(body.scheme_id)
    fields = {field.key for field in program.fields} if program else set()
    if program and set(body.profile) - fields:
        raise HTTPException(
            422, "Additional answers contain fields outside this scheme's approved questionnaire"
        )
    minimal = {key: values[key] for key in fields if key in values}
    report = await service.check(
        EvaluationInput(scheme_id=body.scheme_id, assessed_on=body.assessed_on, profile=minimal)
    )
    return private_notices(report), minimal


async def save_assessment(
    session: AsyncSession, settings: Settings, user_id: UUID, body: AssessmentCreate
) -> Assessment:
    await active_owner(session, user_id)
    raw = body.model_dump_json().encode()
    if not settings.profile_encryption_key:
        raise HTTPException(503, "Private storage is not configured")
    fingerprint = hmac.new(
        settings.profile_encryption_key.get_secret_value().encode(), raw, hashlib.sha256
    ).hexdigest()
    previous = await session.scalar(
        select(Assessment).where(Assessment.user_id == user_id, Assessment.request_key == body.request_key)
    )
    if previous:
        if previous.request_fingerprint != fingerprint:
            raise HTTPException(409, "Assessment request key was used for different inputs")
        return previous
    report, minimal = await evaluate_private(session, settings, user_id, body)
    identifier = uuid4()
    item = Assessment(
        id=identifier,
        user_id=user_id,
        scheme_id=body.scheme_id,
        rule_set_id=report.rule_set.id if report.rule_set else None,
        request_key=body.request_key,
        request_fingerprint=fingerprint,
        encrypted_snapshot=seal(settings, user_id, f"assessment-input:{identifier}", minimal),
        encrypted_report=seal(
            settings, user_id, f"assessment-report:{identifier}", report.model_dump(mode="json")
        ),
        result=report.result.value,
        assessed_on=report.assessed_on,
        allow_reassessment=body.allow_reassessment,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    audit(session, "assessment_saved", user_id, str(identifier))
    await session.commit()
    return item


async def owned_assessment(session: AsyncSession, user_id: UUID, identifier: UUID) -> Assessment:
    item = await session.scalar(
        select(Assessment).where(Assessment.id == identifier, Assessment.user_id == user_id)
    )
    if not item:
        raise HTTPException(404, "Assessment not found")
    return item


def assessment_view(settings: Settings, item: Assessment, *, detailed: bool = False) -> dict[str, Any]:
    report = unseal(settings, item.user_id, f"assessment-report:{item.id}", item.encrypted_report)
    result = {
        "id": str(item.id),
        "scheme_id": str(item.scheme_id),
        "scheme_name": report["scheme_name"],
        "result": item.result,
        "assessment": report["assessment"],
        "rule_set_id": str(item.rule_set_id) if item.rule_set_id else None,
        "rule_version": report["rule_set"]["version_number"] if report["rule_set"] else None,
        "created_at": item.created_at,
        "assessed_on": item.assessed_on,
        "allow_reassessment": item.allow_reassessment,
        "parent_id": str(item.parent_id) if item.parent_id else None,
        "policy_change_id": str(item.policy_change_id) if item.policy_change_id else None,
        "engine_version": report.get("engine_version", "deterministic-v1"),
    }
    if detailed:
        result["report"] = report
    return result


async def reproduce(session: AsyncSession, settings: Settings, item: Assessment) -> dict[str, Any]:
    original = EligibilityReport.model_validate(
        unseal(settings, item.user_id, f"assessment-report:{item.id}", item.encrypted_report)
    )
    if not item.rule_set_id:
        return {
            "matches_original": True,
            "report": original.model_dump(mode="json"),
            "notice": "No approved policy existed in the original assessment. Its saved UNKNOWN result is preserved.",
        }
    snapshot = unseal(settings, item.user_id, f"assessment-input:{item.id}", item.encrypted_snapshot)
    service = EligibilityService(
        SchemeRepository(session), RuleRepository(session), item.assessed_on, rule_set_id=item.rule_set_id
    )
    report = private_notices(await service.check(EvaluationInput(scheme_id=item.scheme_id, profile=snapshot)))
    return {
        "matches_original": report.result == original.result and report.requirements == original.requirements,
        "report": report.model_dump(mode="json"),
        "notice": "Replayed with the original encrypted minimal input, pinned approved rule and original assessment date.",
    }
