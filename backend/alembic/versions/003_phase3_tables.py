"""Phase 3: protocols table + lab_states embedding column

Revision ID: 003
Revises: 002
Create Date: 2024-01-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create protocols table
    op.create_table(
        "protocols",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("lab_state_version", sa.Integer(), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'generated'"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocols_lab_id", "protocols", ["lab_id"])
    op.create_index("ix_protocols_opportunity_id", "protocols", ["opportunity_id"])
    op.create_index("ix_protocols_lab_status", "protocols", ["lab_id", "status"])

    # Enable RLS on protocols
    op.execute("ALTER TABLE protocols ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY protocols_isolation ON protocols
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    # Add embedding column to lab_states (pgvector enabled in migration 001).
    # Existing rows remain NULL; matching service treats NULL as neutral
    # alignment (0.5). New distillations populate this column.
    op.execute("ALTER TABLE lab_states ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX ix_lab_states_embedding ON lab_states "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lab_states_embedding")
    op.execute("ALTER TABLE lab_states DROP COLUMN IF EXISTS embedding")

    op.execute("DROP POLICY IF EXISTS protocols_isolation ON protocols")
    op.drop_table("protocols")
