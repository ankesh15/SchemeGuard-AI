"""Default future account rows to citizen without changing existing roles.

Revision ID: 0004_least_privilege
Revises: 0003_ai_ingestion
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_least_privilege"
down_revision = "0003_ai_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "role", existing_type=sa.String(20), server_default="citizen")


def downgrade() -> None:
    op.alter_column("users", "role", existing_type=sa.String(20), server_default="admin")
