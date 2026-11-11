"""Initial scholarship metadata and immutable document history.

Revision ID: 0001_initial_metadata
Revises: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_metadata"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schemes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("ministry", sa.String(200)),
        sa.Column("department", sa.String(200)),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("applicability", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("applicable_states", postgresql.ARRAY(sa.Text())),
        sa.Column("verified_on", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_schemes"),
        sa.UniqueConstraint("slug", name="uq_schemes_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_schemes_name_not_blank")),
        sa.CheckConstraint(
            "status IN ('listed', 'inactive', 'unknown')", name=op.f("ck_schemes_valid_status")
        ),
        sa.CheckConstraint(
            "(applicability = 'unknown' AND applicable_states IS NULL) OR "
            "(applicability = 'national' AND applicable_states IS NOT NULL AND cardinality(applicable_states) = 0) OR "
            "(applicability = 'states' AND applicable_states IS NOT NULL AND cardinality(applicable_states) > 0)",
            name=op.f("ck_schemes_valid_applicability"),
        ),
    )
    op.create_index("ix_schemes_category", "schemes", ["category"])
    op.create_index("ix_schemes_name_id", "schemes", ["name", "id"])
    op.create_index("ix_schemes_applicable_states", "schemes", ["applicable_states"], postgresql_using="gin")
    op.create_table(
        "scheme_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheme_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supported_fields", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("verification_notes", sa.Text(), nullable=False),
        sa.Column("verified_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_scheme_sources"),
        sa.ForeignKeyConstraint(
            ["scheme_id"], ["schemes.id"], ondelete="RESTRICT", name="fk_scheme_sources_scheme_id_schemes"
        ),
        sa.UniqueConstraint("scheme_id", "url", name="uq_scheme_sources_scheme_url"),
        sa.CheckConstraint("url ~ '^https://[^[:space:]]+$'", name=op.f("ck_scheme_sources_https_url")),
        sa.CheckConstraint(
            "cardinality(supported_fields) > 0", name=op.f("ck_scheme_sources_supported_fields_not_empty")
        ),
    )
    op.create_index("ix_scheme_sources_scheme_id", "scheme_sources", ["scheme_id"])
    op.create_index(
        "uq_scheme_sources_primary",
        "scheme_sources",
        ["scheme_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("content_length_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_on", sa.Date()),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["scheme_sources.id"],
            ondelete="RESTRICT",
            name="fk_document_versions_source_id_scheme_sources",
        ),
        sa.UniqueConstraint("source_id", "version_number", name="uq_document_versions_source_version"),
        sa.UniqueConstraint("source_id", "content_sha256", name="uq_document_versions_source_hash"),
        sa.UniqueConstraint("source_id", "id", name="uq_document_versions_source_id"),
        sa.ForeignKeyConstraint(
            ["source_id", "supersedes_id"],
            ["document_versions.source_id", "document_versions.id"],
            name="fk_document_versions_supersedes_same_source",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version_number > 0", name=op.f("ck_document_versions_positive_version")),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_document_versions_sha256_format")
        ),
        sa.CheckConstraint("content_length_bytes > 0", name=op.f("ck_document_versions_positive_length")),
        sa.CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name=op.f("ck_document_versions_not_self_superseding"),
        ),
    )
    op.create_index("ix_document_versions_source_id", "document_versions", ["source_id"])
    op.execute("""
        CREATE FUNCTION reject_document_version_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'document_versions are immutable; insert a new version'
                USING ERRCODE = '23514';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER document_versions_immutable
        BEFORE UPDATE OR DELETE ON document_versions
        FOR EACH ROW EXECUTE FUNCTION reject_document_version_mutation()
    """)
    op.execute("""
        CREATE TRIGGER document_versions_no_truncate
        BEFORE TRUNCATE ON document_versions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_document_version_mutation()
    """)
    op.execute("""
        CREATE FUNCTION set_scheme_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER schemes_updated_at BEFORE UPDATE ON schemes
        FOR EACH ROW EXECUTE FUNCTION set_scheme_updated_at()
    """)


def downgrade() -> None:
    # Intentionally destructive; only run manually on disposable databases or after backup.
    op.drop_table("document_versions")
    op.execute("DROP FUNCTION reject_document_version_mutation()")
    op.drop_table("scheme_sources")
    op.drop_table("schemes")
    op.execute("DROP FUNCTION set_scheme_updated_at()")
