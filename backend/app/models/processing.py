"""Processing provenance extends existing DocumentVersion; never executable rules."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class SourceAuthorization(Base):
    __tablename__ = "source_authorizations"
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("scheme_sources.id", ondelete="RESTRICT"), primary_key=True
    )
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    url_sha256: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentAsset(Base):
    __tablename__ = "document_assets"
    __table_args__ = (
        CheckConstraint("page_count > 0", name="positive_pages"),
        CheckConstraint("acquisition_method IN ('upload','download')", name="valid_acquisition"),
        CheckConstraint("processing_status IN ('REGISTERED','PARSED','INCOMPLETE')", name="valid_status"),
    )
    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), primary_key=True
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    original_filename: Mapped[str] = mapped_column(String(255))
    acquisition_method: Mapped[str] = mapped_column(String(20))
    page_count: Mapped[int] = mapped_column(Integer)
    pdf_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="REGISTERED", server_default="REGISTERED"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_version_id", "page_number", name="uq_document_pages_number"),
        UniqueConstraint("document_version_id", "id", name="uq_document_pages_document_id"),
        CheckConstraint("page_number > 0", name="positive_page"),
        Index("ix_document_pages_document", "document_version_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    page_number: Mapped[int] = mapped_column(Integer)
    text_content: Mapped[str] = mapped_column(Text)
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    issues: Mapped[list[str]] = mapped_column(JSONB)
    extraction_method: Mapped[str] = mapped_column(String(50), default="pymupdf", server_default="pymupdf")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_version_id", "page_id"],
            ["document_pages.document_version_id", "document_pages.id"],
            name="fk_chunks_same_document",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_version_id", "ordinal", name="uq_document_chunks_ordinal"),
        CheckConstraint("ordinal >= 0 AND char_start >= 0 AND char_end > char_start", name="valid_offsets"),
        Index("ix_document_chunks_document_page", "document_version_id", "page_number"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    page_id: Mapped[UUID] = mapped_column()
    page_number: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    section_identifier: Mapped[str] = mapped_column(String(100))
    text_content: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    extraction_method: Mapped[str] = mapped_column(String(50))
    bounding_box: Mapped[list[float] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        UniqueConstraint("id", "document_version_id", name="uq_processing_jobs_document"),
        CheckConstraint(
            "status IN ('RUNNING','PARSED','PENDING_REVIEW','INCOMPLETE','FAILED')", name="valid_status"
        ),
        Index(
            "uq_processing_jobs_running",
            "document_version_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ),
        Index("ix_processing_jobs_document", "document_version_id", "started_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", server_default="RUNNING")
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(
        String(30), default="candidate-v1", server_default="candidate-v1"
    )
    input_manifest: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    input_chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuleCandidate(Base):
    __tablename__ = "extracted_rule_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "document_version_id"],
            ["document_processing_jobs.id", "document_processing_jobs.document_version_id"],
            name="fk_candidates_job_document",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("job_id", "condition_identifier", name="uq_candidates_job_condition"),
        UniqueConstraint("id", "document_version_id", name="uq_candidates_document"),
        CheckConstraint("logical_relationship IN ('and','or','unspecified')", name="valid_logic"),
        CheckConstraint("review_status = 'PENDING'", name="pending_only"),
        CheckConstraint(
            "validation_status IN ('VALIDATED','NEEDS_REVIEW','INVALID','CONFLICT')",
            name="valid_validation_status",
        ),
        Index("ix_candidates_job", "job_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    condition_identifier: Mapped[str] = mapped_column(String(80))
    logical_relationship: Mapped[str] = mapped_column(
        String(12), default="unspecified", server_default="unspecified"
    )
    label: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mapped_expression: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(30))
    validation_issues: Mapped[list[str]] = mapped_column(JSONB)
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateEvidence(Base):
    __tablename__ = "candidate_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_id", "document_version_id"],
            ["extracted_rule_candidates.id", "extracted_rule_candidates.document_version_id"],
            name="fk_candidate_evidence_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "page_id"],
            ["document_pages.document_version_id", "document_pages.id"],
            name="fk_candidate_evidence_page",
            ondelete="RESTRICT",
        ),
        Index("ix_candidate_evidence_candidate", "candidate_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    page_id: Mapped[UUID] = mapped_column()
    node_key: Mapped[str] = mapped_column(String(80))
    excerpt: Mapped[str] = mapped_column(Text)


class ExtractionError(Base):
    __tablename__ = "extraction_errors"
    __table_args__ = (Index("ix_extraction_errors_job", "job_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("document_processing_jobs.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
