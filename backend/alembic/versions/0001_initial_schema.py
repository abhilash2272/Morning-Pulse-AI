"""Initial schema — sources, companies, documents, story_clusters, document_clusters

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2024-01-15 10:00:00.000000 UTC
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # sources
    # ------------------------------------------------------------------ #
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("reliability_level", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "source_type", name="uq_source_name_type"),
    )
    op.create_index("ix_sources_id", "sources", ["id"])
    op.create_index("ix_sources_source_type", "sources", ["source_type"])

    # ------------------------------------------------------------------ #
    # companies
    # ------------------------------------------------------------------ #
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("investor_relations_url", sa.String(length=512), nullable=True),
        sa.Column("news_url", sa.String(length=512), nullable=True),
        sa.Column("rss_feed_url", sa.String(length=512), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", name="uq_companies_ticker"),
    )
    op.create_index("ix_companies_id", "companies", ["id"])
    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index("ix_companies_cik", "companies", ["cik"])

    # ------------------------------------------------------------------ #
    # story_clusters
    # ------------------------------------------------------------------ #
    op.create_table(
        "story_clusters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("representative_title", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_clusters_id", "story_clusters", ["id"])

    # ------------------------------------------------------------------ #
    # documents
    # ------------------------------------------------------------------ #
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_documents_document_id"),
        sa.UniqueConstraint("url", name="uq_document_url"),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_documents_document_id", "documents", ["document_id"])
    op.create_index("ix_documents_source_type", "documents", ["source_type"])
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_published_at", "documents", ["published_at"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index(
        "ix_documents_source_type_published",
        "documents",
        ["source_type", "published_at"],
    )

    # ------------------------------------------------------------------ #
    # document_clusters (junction table)
    # ------------------------------------------------------------------ #
    op.create_table(
        "document_clusters",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["story_clusters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id", "cluster_id"),
    )


def downgrade() -> None:
    op.drop_table("document_clusters")
    op.drop_table("documents")
    op.drop_table("story_clusters")
    op.drop_table("companies")
    op.drop_table("sources")
