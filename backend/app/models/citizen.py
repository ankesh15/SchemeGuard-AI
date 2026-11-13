"""Private citizen data. Sensitive profiles and reports are encrypted, not broker payloads."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CitizenProfile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    encrypted_data: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="uq_assessment_request"),
        UniqueConstraint("id", "user_id", name="uq_assessment_owner"),
        ForeignKeyConstraint(
            ["parent_id", "user_id"],
            ["assessments.id", "assessments.user_id"],
            ondelete="RESTRICT",
            name="fk_assessment_parent_owner",
        ),
        CheckConstraint("result IN ('PASS','FAIL','UNKNOWN')", name="valid_result"),
        CheckConstraint("rule_set_id IS NOT NULL OR result = 'UNKNOWN'", name="unknown_without_rules"),
        Index("ix_assessments_user_scheme", "user_id", "scheme_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scheme_id: Mapped[UUID] = mapped_column(ForeignKey("schemes.id", ondelete="RESTRICT"))
    rule_set_id: Mapped[UUID | None] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"))
    request_key: Mapped[UUID] = mapped_column()
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    encrypted_snapshot: Mapped[str] = mapped_column(Text)
    encrypted_report: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(10))
    assessed_on: Mapped[date] = mapped_column(Date)
    allow_reassessment: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    parent_id: Mapped[UUID | None] = mapped_column()
    policy_change_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("policy_changes.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    automatic_reassessment: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    policy_updates: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReassessmentEvent(Base):
    __tablename__ = "reassessment_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "policy_change_id", "original_assessment_id", name="uq_reassessment_event"
        ),
        ForeignKeyConstraint(
            ["original_assessment_id", "user_id"],
            ["assessments.id", "assessments.user_id"],
            ondelete="RESTRICT",
            name="fk_reassessment_original_owner",
        ),
        ForeignKeyConstraint(
            ["new_assessment_id", "user_id"],
            ["assessments.id", "assessments.user_id"],
            ondelete="RESTRICT",
            name="fk_reassessment_new_owner",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    policy_change_id: Mapped[UUID] = mapped_column(ForeignKey("policy_changes.id", ondelete="RESTRICT"))
    original_assessment_id: Mapped[UUID] = mapped_column()
    new_assessment_id: Mapped[UUID | None] = mapped_column()
    encrypted_impact: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_event"),
        ForeignKeyConstraint(
            ["assessment_id", "user_id"],
            ["assessments.id", "assessments.user_id"],
            ondelete="RESTRICT",
            name="fk_notification_assessment_owner",
        ),
        Index("ix_notifications_unread", "user_id", "read_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scheme_id: Mapped[UUID] = mapped_column(ForeignKey("schemes.id", ondelete="RESTRICT"))
    policy_change_id: Mapped[UUID] = mapped_column(ForeignKey("policy_changes.id", ondelete="RESTRICT"))
    assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessments.id", ondelete="RESTRICT"))
    notification_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
