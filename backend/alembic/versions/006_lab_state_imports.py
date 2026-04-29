"""Phase 6: lab_state_imports table

Revision ID: 006
Revises: 005
Create Date: 2026-04-28 00:00:00.000000

Tracks an in-flight ORCID-driven publication import: ORCID iD → DOIs →
PubMed abstracts → LLM extraction → proposed state → user-reviewed commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lab_state_imports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("orcid_id", sa.String(19), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "progress",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("proposed_state", postgresql.JSONB(), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lab_state_imports_lab_id", "lab_state_imports", ["lab_id"])
    op.create_index("ix_lab_state_imports_status", "lab_state_imports", ["status"])
    op.create_index(
        "ix_lab_state_imports_lab_created",
        "lab_state_imports",
        ["lab_id", sa.text("created_at DESC")],
    )

    # Tenant isolation — same pattern as agent_sessions (005). FORCE applies
    # the policy to table owners too; without it the migration role silently
    # bypasses RLS.
    op.execute("ALTER TABLE lab_state_imports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lab_state_imports FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY lab_state_imports_isolation ON lab_state_imports
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS lab_state_imports_isolation ON lab_state_imports")
    op.drop_table("lab_state_imports")
