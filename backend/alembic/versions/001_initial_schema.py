"""Initial schema with RLS

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create labs table
    op.create_table(
        "labs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("clerk_org_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_org_id"),
    )
    op.create_index("ix_labs_clerk_org_id", "labs", ["clerk_org_id"])

    # Create lab_states table
    op.create_table(
        "lab_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lab_id", "version", name="uq_lab_states_lab_version"),
    )
    op.create_index("ix_lab_states_lab_id", "lab_states", ["lab_id"])

    # Create raw_signals table
    op.create_table(
        "raw_signals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column(
            "processed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_signals_lab_id", "raw_signals", ["lab_id"])
    op.create_index("ix_raw_signals_signal_type", "raw_signals", ["signal_type"])
    op.create_index("ix_raw_signals_processed", "raw_signals", ["processed"])

    # Create distillation_runs table
    op.create_table(
        "distillation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_state_version", sa.Integer(), nullable=True),
        sa.Column("output_state_version", sa.Integer(), nullable=False),
        sa.Column(
            "signals_processed",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_distillation_runs_lab_id", "distillation_runs", ["lab_id"])

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_lab_id", "audit_logs", ["lab_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Enable Row-Level Security on all tables
    op.execute("ALTER TABLE labs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lab_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE raw_signals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE distillation_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")

    # Create RLS policies
    # Labs: isolate by clerk_org_id
    op.execute("""
        CREATE POLICY labs_isolation ON labs
        USING (clerk_org_id = current_setting('app.current_org_id', true))
    """)

    # Lab states: isolate by lab -> org
    op.execute("""
        CREATE POLICY lab_states_isolation ON lab_states
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    # Raw signals: isolate by lab -> org
    op.execute("""
        CREATE POLICY raw_signals_isolation ON raw_signals
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    # Distillation runs: isolate by lab -> org
    op.execute("""
        CREATE POLICY distillation_runs_isolation ON distillation_runs
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    # Audit logs: isolate by lab -> org (allow null lab_id for system events)
    op.execute("""
        CREATE POLICY audit_logs_isolation ON audit_logs
        USING (
            lab_id IS NULL OR
            lab_id IN (
                SELECT id FROM labs
                WHERE clerk_org_id = current_setting('app.current_org_id', true)
            )
        )
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS audit_logs_isolation ON audit_logs")
    op.execute("DROP POLICY IF EXISTS distillation_runs_isolation ON distillation_runs")
    op.execute("DROP POLICY IF EXISTS raw_signals_isolation ON raw_signals")
    op.execute("DROP POLICY IF EXISTS lab_states_isolation ON lab_states")
    op.execute("DROP POLICY IF EXISTS labs_isolation ON labs")

    # Drop tables in reverse order
    op.drop_table("audit_logs")
    op.drop_table("distillation_runs")
    op.drop_table("raw_signals")
    op.drop_table("lab_states")
    op.drop_table("labs")
