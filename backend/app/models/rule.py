from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.scheme import DocumentVersion


class RuleSet(Base):
    __tablename__ = "rule_sets"
    __table_args__ = (
        UniqueConstraint("scheme_id", "version_number", name="uq_rule_sets_scheme_version"),
        UniqueConstraint("id", "source_document_version_id", name="uq_rule_sets_id_document"),
        CheckConstraint("version_number > 0", name="positive_version"),
        CheckConstraint("approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')", name="valid_approval_status"),
        CheckConstraint("logical_operator IN ('and', 'or')", name="valid_logic"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="valid_effective_dates"
        ),
        CheckConstraint(
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL AND approved_by IS NOT NULL "
            "AND length(trim(approved_by)) > 0 AND approval_basis IN ('human_review', 'synthetic_fixture')) OR "
            "(approval_status <> 'APPROVED' AND approved_at IS NULL AND approved_by IS NULL AND approval_basis IS NULL)",
            name="approval_metadata",
        ),
        Index("ix_rule_sets_selection", "scheme_id", "approval_status", "effective_from", "version_number"),
        Index("ix_rule_sets_source_document", "source_document_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheme_id: Mapped[UUID] = mapped_column(ForeignKey("schemes.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    approval_status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    logical_operator: Mapped[str] = mapped_column(String(3), default="and", server_default="and")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    profile_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    scope_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approval_basis: Mapped[str | None] = mapped_column(String(30))

    conditions: Mapped[list["RuleCondition"]] = relationship(
        back_populates="rule_set", order_by="RuleCondition.position", lazy="raise", passive_deletes="all"
    )
    document: Mapped[DocumentVersion] = relationship(lazy="raise")


class RuleCondition(Base):
    __tablename__ = "rule_conditions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "condition_key", name="uq_rule_conditions_key"),
        UniqueConstraint("rule_set_id", "position", name="uq_rule_conditions_position"),
        UniqueConstraint("rule_set_id", "id", name="uq_rule_conditions_set_id"),
        CheckConstraint("position >= 0", name="positive_position"),
        Index("ix_rule_conditions_rule_set_id", "rule_set_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_set_id: Mapped[UUID] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"))
    condition_key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    expression: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rule_set: Mapped[RuleSet] = relationship(back_populates="conditions", lazy="raise")
    evidence: Mapped[list["RuleEvidence"]] = relationship(
        back_populates="condition", lazy="raise", passive_deletes="all", order_by="RuleEvidence.locator"
    )


class RuleEvidence(Base):
    __tablename__ = "rule_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "condition_id"],
            ["rule_conditions.rule_set_id", "rule_conditions.id"],
            ondelete="RESTRICT",
            name="fk_rule_evidence_condition_same_set",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "document_version_id"],
            ["rule_sets.id", "rule_sets.source_document_version_id"],
            ondelete="RESTRICT",
            name="fk_rule_evidence_document_same_set",
        ),
        UniqueConstraint("condition_id", "document_version_id", "locator", name="uq_rule_evidence_reference"),
        CheckConstraint("length(trim(locator)) > 0 AND length(trim(excerpt)) > 0", name="nonempty_evidence"),
        Index("ix_rule_evidence_rule_set_id", "rule_set_id"),
        Index("ix_rule_evidence_condition_id", "condition_id"),
        Index("ix_rule_evidence_document_version_id", "document_version_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_set_id: Mapped[UUID] = mapped_column()
    condition_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    locator: Mapped[str] = mapped_column(String(200))
    excerpt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    condition: Mapped[RuleCondition] = relationship(back_populates="evidence", lazy="raise")
