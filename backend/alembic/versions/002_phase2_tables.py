"""Phase 2: literature, opportunities, API keys tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add search_config to labs table for scheduled literature scans
    op.add_column(
        "labs",
        sa.Column("search_config", postgresql.JSONB(), nullable=True),
    )

    # Create papers table
    op.create_table(
        "papers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("pmid", sa.String(20), nullable=True),
        sa.Column("semantic_scholar_id", sa.String(50), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=True),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("mesh_terms", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("metadata_", postgresql.JSONB(), nullable=True),
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
    op.create_index("ix_papers_lab_id", "papers", ["lab_id"])
    op.create_index("ix_papers_doi", "papers", ["doi"])
    op.create_index("ix_papers_pmid", "papers", ["pmid"])
    # Partial unique: one DOI per lab
    op.execute(
        "CREATE UNIQUE INDEX uq_papers_lab_doi ON papers (lab_id, doi) WHERE doi IS NOT NULL"
    )
    # Partial unique: one PMID per lab
    op.execute(
        "CREATE UNIQUE INDEX uq_papers_lab_pmid ON papers (lab_id, pmid) WHERE pmid IS NOT NULL"
    )

    # Add embedding column (pgvector already enabled in migration 001)
    op.execute("ALTER TABLE papers ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX ix_papers_embedding ON papers USING hnsw (embedding vector_cosine_ops)"
    )

    # Create opportunities table
    op.create_table(
        "opportunities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_equipment", postgresql.JSONB(), nullable=False),
        sa.Column("required_techniques", postgresql.JSONB(), nullable=False),
        sa.Column("required_expertise", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_complexity", sa.String(20), nullable=False),
        sa.Column(
            "source_paper_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("extraction_prompt_version", sa.String(50), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
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
    op.create_index("ix_opportunities_lab_id", "opportunities", ["lab_id"])
    op.create_index("ix_opportunities_status", "opportunities", ["status"])

    # Add embedding column for opportunities
    op.execute("ALTER TABLE opportunities ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX ix_opportunities_embedding ON opportunities "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Create literature_scans table
    op.create_table(
        "literature_scans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_type", sa.String(20), nullable=False),
        sa.Column("query_params", postgresql.JSONB(), nullable=False),
        sa.Column(
            "papers_found", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "papers_new", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "opportunities_extracted",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_literature_scans_lab_id", "literature_scans", ["lab_id"])
    op.create_index("ix_literature_scans_status", "literature_scans", ["status"])

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_lab_id", "api_keys", ["lab_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # Enable Row-Level Security on new tables
    op.execute("ALTER TABLE papers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE literature_scans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")

    # Create RLS policies (same pattern as migration 001)
    op.execute("""
        CREATE POLICY papers_isolation ON papers
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    op.execute("""
        CREATE POLICY opportunities_isolation ON opportunities
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    op.execute("""
        CREATE POLICY literature_scans_isolation ON literature_scans
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)

    op.execute("""
        CREATE POLICY api_keys_isolation ON api_keys
        USING (lab_id IN (
            SELECT id FROM labs
            WHERE clerk_org_id = current_setting('app.current_org_id', true)
        ))
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS api_keys_isolation ON api_keys")
    op.execute("DROP POLICY IF EXISTS literature_scans_isolation ON literature_scans")
    op.execute("DROP POLICY IF EXISTS opportunities_isolation ON opportunities")
    op.execute("DROP POLICY IF EXISTS papers_isolation ON papers")

    # Drop tables in reverse order
    op.drop_table("api_keys")
    op.drop_table("literature_scans")
    op.drop_table("opportunities")
    op.drop_table("papers")

    # Remove search_config from labs
    op.drop_column("labs", "search_config")
