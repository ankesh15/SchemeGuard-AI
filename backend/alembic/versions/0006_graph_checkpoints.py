"""Official LangGraph Postgres checkpoint schema, pinned to saver 3.2.0.

Revision ID: 0006_graph_checkpoints
Revises: 0005_workflow_rag
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_graph_checkpoints"
down_revision = "0005_workflow_rag"
branch_labels = None
depends_on = None

# Vendor DDL from BasePostgresSaver.MIGRATIONS. New empty tables need no
# concurrent index build, so keep this migration fully transactional.
MIGRATIONS = [
    "CREATE TABLE IF NOT EXISTS checkpoint_migrations (\n    v INTEGER PRIMARY KEY\n);",
    "CREATE TABLE IF NOT EXISTS checkpoints (\n    thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT '',\n    checkpoint_id TEXT NOT NULL,\n    parent_checkpoint_id TEXT,\n    type TEXT,\n    checkpoint JSONB NOT NULL,\n    metadata JSONB NOT NULL DEFAULT '{}',\n    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)\n);",
    "CREATE TABLE IF NOT EXISTS checkpoint_blobs (\n    thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT '',\n    channel TEXT NOT NULL,\n    version TEXT NOT NULL,\n    type TEXT NOT NULL,\n    blob BYTEA,\n    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)\n);",
    "CREATE TABLE IF NOT EXISTS checkpoint_writes (\n    thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT '',\n    checkpoint_id TEXT NOT NULL,\n    task_id TEXT NOT NULL,\n    idx INTEGER NOT NULL,\n    channel TEXT NOT NULL,\n    type TEXT,\n    blob BYTEA NOT NULL,\n    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)\n);",
    "ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP not null;",
    "SELECT 1;",
    "\n    CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);\n    ",
    "\n    CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);\n    ",
    "\n    CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);\n    ",
    "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT '';",
]


def upgrade() -> None:
    connection = op.get_bind()
    previous = connection.exec_driver_sql("SHOW search_path").scalar_one()
    op.execute("CREATE SCHEMA IF NOT EXISTS sg_checkpoints")
    op.execute("SET LOCAL search_path TO sg_checkpoints, public")
    for number, statement in enumerate(MIGRATIONS):
        op.execute(statement)
        connection.execute(
            sa.text("INSERT INTO checkpoint_migrations (v) VALUES (:number) ON CONFLICT DO NOTHING"),
            {"number": number},
        )
    connection.execute(sa.text("SELECT set_config('search_path', :previous, true)"), {"previous": previous})


def downgrade() -> None:
    # Destructive checkpoint removal; exercised only in disposable test DBs.
    op.execute("DROP SCHEMA sg_checkpoints CASCADE")
