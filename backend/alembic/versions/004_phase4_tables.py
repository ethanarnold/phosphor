"""Phase 4: documents + adoption_events tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # documents
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parse_error", sa.String(2000), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_lab_id", "documents", ["lab_id"])
    op.create_index("ix_documents_lab_status", "documents", ["lab_id", "status"])

    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY documents_isolation ON documents
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    # adoption_events — lightweight event stream for Phase 4 metrics
    op.create_table(
        "adoption_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_adoption_events_lab_id", "adoption_events", ["lab_id"])
    op.create_index(
        "ix_adoption_events_lab_type_time",
        "adoption_events",
        ["lab_id", "event_type", "created_at"],
    )

    op.execute("ALTER TABLE adoption_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY adoption_events_isolation ON adoption_events
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS adoption_events_isolation ON adoption_events")
    op.drop_table("adoption_events")
    op.execute("DROP POLICY IF EXISTS documents_isolation ON documents")
    op.drop_table("documents")
