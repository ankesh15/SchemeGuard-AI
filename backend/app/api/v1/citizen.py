from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import delete, func, select, update

from app.api.v1.admin_auth import DB
from app.api.v1.citizen_auth import Citizen
from app.auth.encryption import unseal
from app.auth.security import audit, limit
from app.models import (
    Assessment,
    CitizenProfile,
    Notification,
    PolicyChange,
    ReassessmentEvent,
)
from app.schemas.citizen import AssessmentCreate, Preferences, ProfileData
from app.services.citizen import (
    active_owner,
    assessment_view,
    owned_assessment,
    preference,
    profile_read,
    put_profile,
    reproduce,
    save_assessment,
)

router = APIRouter(tags=["private citizen workspace"])


@router.get("/profiles/options")
async def profile_options(user: Citizen) -> dict[str, Any]:
    from app.ai.validation import FIELDS
    from app.core.enums import IndianState

    reserved = {
        "state",
        "age_years",
        "annual_family_income_inr",
        "course_level",
        "current_student",
        "occupation",
    }
    fields: list[dict[str, Any]] = [
        {
            "key": key,
            "label": label,
            "value_type": value_type,
            "section": "Additional scheme fields",
            "help_text": f"Input units: {units}." if units else "Optional. Leave unknown if not applicable.",
            "choices": [],
            "integer": False,
            "minimum": 0 if value_type == "number" else None,
            "maximum": 100 if key == "disability_percent" else None,
            "visible_when": None,
        }
        for key, (label, value_type, units) in FIELDS.items()
        if key not in reserved
    ]
    fields += [
        {
            "key": key,
            "label": label,
            "value_type": value_type,
            "section": "Fictional demo fields",
            "help_text": "Used only by the clearly labeled fictional development scholarship.",
            "choices": [],
            "integer": False,
            "visible_when": None,
        }
        for key, label, value_type in [
            ("course", "Fictional demo course", "string"),
            (
                "requests_disability_support",
                "Requesting disability support in the fictional demo?",
                "boolean",
            ),
        ]
    ]
    return {"states": [state.value for state in IndianState], "fields": fields}


@router.get("/profiles/me")
async def profile(request: Request, user: Citizen, session: DB) -> dict[str, Any]:
    return await profile_read(session, request.app.state.settings, user.id)


@router.put("/profiles/me")
async def update_profile(body: ProfileData, request: Request, user: Citizen, session: DB) -> dict[str, Any]:
    return await put_profile(session, request.app.state.settings, user.id, body)


@router.delete("/profiles/me", status_code=204)
async def delete_profile(user: Citizen, session: DB) -> None:
    await active_owner(session, user.id)
    await session.execute(delete(CitizenProfile).where(CitizenProfile.user_id == user.id))
    audit(session, "citizen_profile_deleted", user.id)
    await session.commit()


@router.post("/assessments", status_code=201)
async def create_assessment(
    body: AssessmentCreate, request: Request, user: Citizen, session: DB
) -> dict[str, Any]:
    await limit(session, f"save-assessment:{user.id}", 30, 900)
    item = await save_assessment(session, request.app.state.settings, user.id, body)
    return assessment_view(request.app.state.settings, item, detailed=True)


@router.get("/assessments")
async def assessments(
    request: Request,
    user: Citizen,
    session: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(Assessment).where(Assessment.user_id == user.id)
    items = await session.scalars(
        statement.order_by(Assessment.created_at.desc(), Assessment.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [assessment_view(request.app.state.settings, item) for item in items],
        "total": await session.scalar(select(func.count()).select_from(statement.subquery())),
        "page": page,
        "page_size": page_size,
    }


@router.get("/assessments/{identifier}")
async def assessment_detail(identifier: UUID, request: Request, user: Citizen, session: DB) -> dict[str, Any]:
    item = await owned_assessment(session, user.id, identifier)
    impact = await session.scalar(
        select(ReassessmentEvent).where(
            ReassessmentEvent.user_id == user.id, ReassessmentEvent.new_assessment_id == identifier
        )
    )
    from app.services.currency import outdated_schemes

    outdated = item.scheme_id in await outdated_schemes(session, [item.scheme_id])
    return assessment_view(request.app.state.settings, item, detailed=True) | {
        "current_policy_currency": "POTENTIALLY_OUTDATED" if outdated else "CHECK_OFFICIAL_SOURCE",
        "impact": unseal(request.app.state.settings, user.id, f"impact:{impact.id}", impact.encrypted_impact)
        if impact
        else None,
    }


@router.post("/assessments/{identifier}/reproduce")
async def reproduce_assessment(
    identifier: UUID, request: Request, user: Citizen, session: DB
) -> dict[str, Any]:
    item = await owned_assessment(session, user.id, identifier)
    return await reproduce(session, request.app.state.settings, item)


@router.get("/notification-preferences")
async def preferences(user: Citizen, session: DB) -> Preferences:
    row = await preference(session, user.id)
    await session.commit()
    return Preferences(
        in_app=row.in_app,
        automatic_reassessment=row.automatic_reassessment,
        policy_updates=row.policy_updates,
    )


@router.put("/notification-preferences")
async def update_preferences(body: Preferences, user: Citizen, session: DB) -> Preferences:
    await active_owner(session, user.id)
    row = await preference(session, user.id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    audit(session, "notification_preferences_updated", user.id)
    await session.commit()
    return body


@router.get("/notifications")
async def notifications(
    user: Citizen,
    session: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
) -> dict[str, Any]:
    statement = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    items = await session.scalars(
        statement.order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [
            {
                column.name: getattr(item, column.name)
                for column in Notification.__table__.columns
                if column.name not in {"user_id", "dedupe_key"}
            }
            for item in items
        ],
        "total": await session.scalar(select(func.count()).select_from(statement.subquery())),
        "unread_count": await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        ),
        "page": page,
        "page_size": page_size,
    }


@router.post("/notifications/read-all", status_code=204)
async def mark_all_read(user: Citizen, session: DB) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()


@router.post("/notifications/{identifier}/read", status_code=204)
async def mark_read(identifier: UUID, user: Citizen, session: DB) -> None:
    item = await session.scalar(
        select(Notification).where(Notification.id == identifier, Notification.user_id == user.id)
    )
    if not item:
        raise HTTPException(404, "Notification not found")
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
    await session.commit()


@router.get("/dashboard")
async def dashboard(request: Request, user: Citizen, session: DB) -> dict[str, Any]:
    saved = await assessments(request, user, session, page=1, page_size=5)
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    updates = await related_updates(user, session)
    profile_info = await profile_read(session, request.app.state.settings, user.id)
    from app.repositories.scheme import SchemeRepository
    from app.schemas.scheme import SchemeQuery
    from app.services.scheme import SchemeService

    discovery = await SchemeService(SchemeRepository(session)).list(
        SchemeQuery.model_validate({"state": profile_info["profile"]["state"], "page_size": 3})
    )
    return {
        "relevant_schemes": [item.model_dump(mode="json") for item in discovery.items],
        "discovery_notice": "Geographical discovery metadata only; these suggestions do not establish eligibility.",
        "username": user.username,
        "profile": profile_info,
        "recent_assessments": saved["items"],
        "assessment_count": saved["total"],
        "unread_count": unread,
        "policy_updates": updates["items"][:5],
    }


@router.get("/me/policy-updates")
async def related_updates(user: Citizen, session: DB) -> dict[str, Any]:
    interested = select(Assessment.scheme_id).where(Assessment.user_id == user.id)
    changes = await session.scalars(
        select(PolicyChange)
        .where(
            PolicyChange.verification_status == "APPROVED",
            PolicyChange.new_rule_set_id.is_not(None),
            PolicyChange.scheme_id.in_(interested),
        )
        .order_by(PolicyChange.approved_at.desc())
        .limit(100)
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "scheme_id": str(item.scheme_id),
                "classification": item.classification,
                "published_at": item.approved_at,
                "effective_from": item.effective_from,
                "new_rule_set_id": str(item.new_rule_set_id),
            }
            for item in changes
        ]
    }
