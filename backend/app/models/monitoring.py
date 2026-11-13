"""Durable queue and opt-in source/policy monitoring provenance."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('QUEUED','RUNNING','RETRY','SUCCEEDED','FAILED')", name="valid_status"),
        Index("ix_jobs_dispatch", "status", "available_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(30))
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceMonitor(Base):
    __tablename__ = "source_monitoring_config"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily','weekly') AND hour_utc BETWEEN 0 AND 23 AND weekday BETWEEN 0 AND 6 AND min_interval_seconds >= 60",
            name="valid_schedule",
        ),
        Index("ix_monitors_due", "enabled", "next_check_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("scheme_sources.id", ondelete="RESTRICT"), unique=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    frequency: Mapped[str] = mapped_column(String(10), default="weekly", server_default="weekly")
    hour_utc: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    min_interval_seconds: Mapped[int] = mapped_column(Integer, default=3600, server_default="3600")
    access_notes: Mapped[str] = mapped_column(Text)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(
        String(30), default="VERIFIED", server_default="VERIFIED"
    )
    etag: Mapped[str | None] = mapped_column(String(512))
    last_modified: Mapped[str | None] = mapped_column(String(512))
    last_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"
    __table_args__ = (Index("ix_runs_monitor", "monitor_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID] = mapped_column(ForeignKey("source_monitoring_config.id", ondelete="RESTRICT"))
    job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="RESTRICT"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", server_default="QUEUED")
    old_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    new_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    response_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PolicyChange(Base):
    __tablename__ = "policy_changes"
    __table_args__ = (Index("ix_policy_changes_status", "verification_status", "detected_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheme_id: Mapped[UUID] = mapped_column(ForeignKey("schemes.id", ondelete="RESTRICT"))
    source_id: Mapped[UUID] = mapped_column(ForeignKey("scheme_sources.id", ondelete="RESTRICT"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("monitoring_runs.id", ondelete="RESTRICT"), unique=True)
    old_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    new_document_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    old_rule_set_id: Mapped[UUID | None] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"))
    workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_workflows.id", ondelete="RESTRICT"), unique=True
    )
    new_rule_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), unique=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(30), default="PENDING_REVIEW", server_default="PENDING_REVIEW"
    )
    classification: Mapped[str] = mapped_column(
        String(30), default="INCONCLUSIVE", server_default="INCONCLUSIVE"
    )
    compared_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    clarification_revision: Mapped[int | None] = mapped_column(Integer)
    effective_from: Mapped[date | None] = mapped_column(Date)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyChangeDetail(Base):
    __tablename__ = "policy_change_details"
    __table_args__ = (
        UniqueConstraint("change_id", "revision_number", "condition_key", name="uq_change_detail_revision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("policy_changes.id", ondelete="RESTRICT"))
    revision_number: Mapped[int] = mapped_column(Integer)
    condition_key: Mapped[str] = mapped_column(String(200))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeReviewEvent(Base):
    __tablename__ = "policy_change_review_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("policy_changes.id", ondelete="RESTRICT"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text)
    revision_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
