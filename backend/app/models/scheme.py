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
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Scheme(Base):
    __tablename__ = "schemes"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("status IN ('listed', 'inactive', 'unknown')", name="valid_status"),
        CheckConstraint(
            "(applicability = 'unknown' AND applicable_states IS NULL) OR "
            "(applicability = 'national' AND applicable_states IS NOT NULL AND cardinality(applicable_states) = 0) OR "
            "(applicability = 'states' AND applicable_states IS NOT NULL AND cardinality(applicable_states) > 0)",
            name="valid_applicability",
        ),
        Index("ix_schemes_category", "category"),
        Index("ix_schemes_name_id", "name", "id"),
        Index("ix_schemes_applicable_states", "applicable_states", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(150), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    ministry: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    applicability: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    applicable_states: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    verified_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list["SchemeSource"]] = relationship(
        back_populates="scheme", lazy="raise", passive_deletes="all", order_by="SchemeSource.url"
    )

    @property
    def official_source_url(self) -> str | None:
        return next((source.url for source in self.sources if source.is_primary), None)


class SchemeSource(Base):
    __tablename__ = "scheme_sources"
    __table_args__ = (
        UniqueConstraint("scheme_id", "url", name="uq_scheme_sources_scheme_url"),
        CheckConstraint("url ~ '^https://[^[:space:]]+$'", name="https_url"),
        CheckConstraint("cardinality(supported_fields) > 0", name="supported_fields_not_empty"),
        Index("ix_scheme_sources_scheme_id", "scheme_id"),
        Index("uq_scheme_sources_primary", "scheme_id", unique=True, postgresql_where=text("is_primary")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheme_id: Mapped[UUID] = mapped_column(ForeignKey("schemes.id", ondelete="RESTRICT"))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    supported_fields: Mapped[list[str]] = mapped_column(ARRAY(Text))
    verification_notes: Mapped[str] = mapped_column(Text)
    verified_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scheme: Mapped[Scheme] = relationship(back_populates="sources", lazy="raise")
    document_versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="source", lazy="raise", passive_deletes="all"
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "version_number", name="uq_document_versions_source_version"),
        UniqueConstraint("source_id", "content_sha256", name="uq_document_versions_source_hash"),
        UniqueConstraint("source_id", "id", name="uq_document_versions_source_id"),
        ForeignKeyConstraint(
            ["source_id", "supersedes_id"],
            ["document_versions.source_id", "document_versions.id"],
            name="fk_document_versions_supersedes_same_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number > 0", name="positive_version"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint("content_length_bytes > 0", name="positive_length"),
        CheckConstraint("supersedes_id IS NULL OR supersedes_id <> id", name="not_self_superseding"),
        Index("ix_document_versions_source_id", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("scheme_sources.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64))
    content_length_bytes: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_on: Mapped[date | None] = mapped_column(Date)
    supersedes_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[SchemeSource] = relationship(
        back_populates="document_versions", foreign_keys=[source_id], lazy="raise"
    )
