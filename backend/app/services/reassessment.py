"""Verified material publications trigger owner-scoped deterministic reassessment."""

from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.encryption import seal, unseal
from app.core.config import Settings
from app.models import (
    Assessment,
    Notification,
    PolicyChange,
    PolicyChangeDetail,
    ReassessmentEvent,
    RuleSet,
    User,
)
from app.schemas.citizen import AssessmentCreate
from app.schemas.eligibility import EligibilityReport
from app.services.citizen import evaluate_private, preference
from app.services.jobs import enqueue


async def queue_reassessment(session: AsyncSession, change: PolicyChange) -> None:
    if change.verification_status != "APPROVED" or not change.new_rule_set_id:
        return
    available = datetime.now(UTC)
    if change.effective_from:
        available = max(
            available,
            datetime.combine(change.effective_from, time.min, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(
                UTC
            ),
        )
    await enqueue(
        session, "REASSESS", f"reassess:{change.id}", {"change_id": str(change.id)}, available_at=available
    )


def flatten_results(report: EligibilityReport) -> dict[str, str]:
    from app.services.policy_diff import stable_key

    result = {}

    def visit(node: Any) -> None:
        if node.kind == "comparison":
            result[stable_key(node.key)] = node.result.value
        for child in node.children:
            visit(child)

    for node in report.requirements:
        visit(node)
    return result


async def reassess_change(session: AsyncSession, settings: Settings, identifier: UUID) -> dict[str, Any]:
    change = await session.get(PolicyChange, identifier)
    if not change or change.verification_status != "APPROVED" or not change.new_rule_set_id:
        return {"skipped": "unapproved_change"}
    if change.approved_at is None:
        return {"skipped": "approval_timestamp_missing"}
    scheme_id, change_id, approved_at = change.scheme_id, change.id, change.approved_at
    new_rule_id, classification = change.new_rule_set_id, change.classification
    rule = await session.get(RuleSet, new_rule_id)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not rule or rule.approval_status != "APPROVED" or rule.effective_from > today:
        return {"skipped": "not_effective"}
    # List IDs only. Each account is locked/rechecked before any private read.
    user_ids = list(
        await session.scalars(
            select(Assessment.user_id)
            .where(Assessment.scheme_id == scheme_id, Assessment.created_at <= approved_at)
            .distinct()
        )
    )
    await session.commit()
    assessed = notified = 0
    for user_id in user_ids:
        # Commit per account: a retry skips completed events; deleted/disabled
        # accounts cannot be resurrected by delayed jobs.
        user = await session.scalar(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
        if not user or not user.is_active or user.role != "citizen":
            await session.rollback()
            continue
        prefs = await preference(session, user_id)
        original = await session.scalar(
            select(Assessment)
            .where(Assessment.user_id == user_id, Assessment.scheme_id == scheme_id)
            .order_by(Assessment.created_at.desc(), Assessment.id.desc())
            .limit(1)
        )
        if not original or original.rule_set_id == new_rule_id or original.created_at > approved_at:
            await session.commit()
            continue
        event_id = uuid5(change_id, f"reassessment:{user_id}:{original.id}")
        if await session.get(ReassessmentEvent, event_id):
            await session.commit()
            continue
        old_report = EligibilityReport.model_validate(
            unseal(settings, user_id, f"assessment-report:{original.id}", original.encrypted_report)
        )
        new_id = None
        impact: dict[str, Any] = {
            "original_assessment_id": str(original.id),
            "old_result": original.result,
            "policy_change_id": str(change_id),
            "notice": "Original assessment is preserved. A new assessment uses the currently authorized profile and applicable approved policy.",
        }
        kind = "POLICY_UPDATE_PUBLISHED"
        if prefs.automatic_reassessment and original.allow_reassessment and classification == "MATERIAL":
            body = AssessmentCreate(
                scheme_id=scheme_id,
                request_key=event_id,
                use_saved_profile=True,
                allow_reassessment=True,
            )
            report, minimal = await evaluate_private(session, settings, user_id, body)
            if not report.rule_set or report.rule_set.id != new_rule_id:
                # A later publication may already supersede this queued change.
                await session.commit()
                continue
            new_id = uuid5(event_id, "assessment")
            item = Assessment(
                id=new_id,
                user_id=user_id,
                scheme_id=scheme_id,
                rule_set_id=new_rule_id,
                request_key=event_id,
                request_fingerprint=event_id.hex.ljust(64, "0"),
                encrypted_snapshot=seal(settings, user_id, f"assessment-input:{new_id}", minimal),
                encrypted_report=seal(
                    settings, user_id, f"assessment-report:{new_id}", report.model_dump(mode="json")
                ),
                result=report.result.value,
                assessed_on=report.assessed_on,
                allow_reassessment=True,
                parent_id=original.id,
                policy_change_id=change_id,
                created_at=datetime.now(UTC),
            )
            session.add(item)
            await session.flush()
            previous = flatten_results(old_report)
            current = flatten_results(report)
            changed = [
                {
                    "condition_key": key,
                    "old_result": previous.get(key, "NOT_PRESENT"),
                    "new_result": current.get(key, "NOT_PRESENT"),
                }
                for key in sorted(previous.keys() | current.keys())
                if previous.get(key) != current.get(key)
            ]
            impact.update(
                new_assessment_id=str(new_id),
                new_result=report.result.value,
                result_changed=report.result != old_report.result,
                condition_changes=changed,
                missing_fields=[field.key for field in report.missing_fields],
                old_rule_set_id=str(original.rule_set_id) if original.rule_set_id else None,
                new_rule_set_id=str(new_rule_id),
            )
            kind = (
                "NEW_INFORMATION_REQUIRED"
                if report.missing_fields
                else "ELIGIBILITY_CONDITION_CHANGED"
                if report.result != old_report.result
                else "PREVIOUS_ASSESSMENT_AFFECTED"
            )
            assessed += 1
        else:
            impact["reassessment_skipped"] = (
                "disabled_by_preference_or_assessment_consent_or_nonmaterial_change"
            )
        session.add(
            ReassessmentEvent(
                id=event_id,
                user_id=user_id,
                policy_change_id=change_id,
                original_assessment_id=original.id,
                new_assessment_id=new_id,
                encrypted_impact=seal(settings, user_id, f"impact:{event_id}", impact),
            )
        )
        if prefs.in_app and (kind != "POLICY_UPDATE_PUBLISHED" or prefs.policy_updates):
            deadline = await session.scalar(
                select(PolicyChangeDetail.id)
                .where(
                    PolicyChangeDetail.change_id == change_id,
                    PolicyChangeDetail.detail["field"].astext == "application_deadline",
                    PolicyChangeDetail.detail["change_type"].astext == "APPLICATION_DEADLINE_CHANGED",
                )
                .limit(1)
            )
            if deadline and kind == "POLICY_UPDATE_PUBLISHED":
                kind = "APPLICATION_DEADLINE_CHANGED"
            session.add(
                Notification(
                    id=uuid5(event_id, "notification"),
                    user_id=user_id,
                    scheme_id=scheme_id,
                    policy_change_id=change_id,
                    assessment_id=new_id or original.id,
                    notification_type=kind,
                    title="A verified policy update affects a saved scheme",
                    description="Review the published policy version, source evidence and any updated assessment. This is informational and is not government approval.",
                    dedupe_key=f"policy:{change_id}:assessment:{original.id}",
                )
            )
            notified += 1
        await session.commit()
    return {"reassessed": assessed, "notified": notified, "affected_accounts": len(user_ids)}
