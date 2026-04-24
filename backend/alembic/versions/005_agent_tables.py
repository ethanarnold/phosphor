"""Phase 5: agent_sessions + agent_messages tables

Revision ID: 005
Revises: 004
Create Date: 2026-04-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("input_text", sa.String(8000), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("turn_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("final_answer", sa.String(16000), nullable=True),
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
    op.create_index("ix_agent_sessions_lab_id", "agent_sessions", ["lab_id"])
    op.create_index("ix_agent_sessions_purpose", "agent_sessions", ["purpose"])
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"])
    op.create_index(
        "ix_agent_sessions_lab_status_created",
        "agent_sessions",
        ["lab_id", "status", "created_at"],
    )

    # Row-level security — an agent session inherits the tenancy of its lab.
    op.execute("ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY agent_sessions_isolation ON agent_sessions
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    op.create_table(
        "agent_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.String(32000), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("tool_args_json", postgresql.JSONB(), nullable=True),
        sa.Column("tool_result_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq", name="uq_agent_messages_session_seq"),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])

    # Messages inherit their session's lab tenancy via the join.
    op.execute("ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY agent_messages_isolation ON agent_messages
        USING (session_id IN (
            SELECT s.id FROM agent_sessions s
            JOIN labs l ON l.id = s.lab_id
            WHERE l.clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_messages_isolation ON agent_messages")
    op.drop_table("agent_messages")
    op.execute("DROP POLICY IF EXISTS agent_sessions_isolation ON agent_sessions")
    op.drop_table("agent_sessions")
