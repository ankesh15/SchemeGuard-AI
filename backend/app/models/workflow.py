"""Durable workflow metadata and immutable human-review/publication records."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentWorkflow(Base):
    __tablename__ = "agent_workflows"
    __table_args__ = (
        UniqueConstraint("requested_by", "request_key", name="uq_workflow_request"),
        CheckConstraint(
            "status IN ('PROCESSING','PENDING_REVIEW','APPROVED','REJECTED','FAILED','CANCELLED')",
            name="valid_status",
        ),
        CheckConstraint("attempts >= 0", name="valid_attempts"),
        Index("ix_workflows_status_created", "status", "created_at"),
        Index("ix_workflows_document", "document_version_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[UUID] = mapped_column()
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    graph_version: Mapped[str] = mapped_column(String(30), default="policy-v1", server_default="policy-v1")
    extraction_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_processing_jobs.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(30), default="PROCESSING", server_default="PROCESSING")
    stage: Mapped[str] = mapped_column(String(40), default="prepare", server_default="prepare")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    published_rule_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_workflow", "workflow_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("agent_workflows.id", ondelete="RESTRICT"))
    stage: Mapped[str] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyReview(Base):
    __tablename__ = "policy_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_REVIEW','APPROVED','REJECTED','CANCELLED')", name="valid_status"
        ),
        Index("ix_reviews_status", "status", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_workflows.id", ondelete="RESTRICT"), unique=True
    )
    original_proposal: Mapped[dict[str, Any]] = mapped_column(JSONB)
    verification_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW", server_default="PENDING_REVIEW")
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewRevision(Base):
    __tablename__ = "review_revisions"
    __table_args__ = (UniqueConstraint("review_id", "revision_number", name="uq_review_revision"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(ForeignKey("policy_reviews.id", ondelete="RESTRICT"))
    revision_number: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB)
    proposal_sha256: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (CheckConstraint("action IN ('APPROVE','REJECT')", name="valid_action"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(ForeignKey("policy_reviews.id", ondelete="RESTRICT"), unique=True)
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("review_revisions.id", ondelete="RESTRICT"))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str] = mapped_column(Text)
    attestations: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RulePublication(Base):
    __tablename__ = "rule_publications"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_workflows.id", ondelete="RESTRICT"), unique=True
    )
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_decisions.id", ondelete="RESTRICT"), unique=True
    )
    rule_set_id: Mapped[UUID] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"), unique=True)
    replaced_rule_set_ids: Mapped[list[str]] = mapped_column(JSONB)
    applicability_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "provider", "model", name="uq_chunk_embedding_model"),
        CheckConstraint("dimensions = 768", name="supported_dimension"),
        Index("ix_embeddings_namespace", "provider", "model"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("document_chunks.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int] = mapped_column(Integer, default=768, server_default="768")
    content_sha256: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
