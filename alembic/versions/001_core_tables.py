"""Create core pipeline tables: sources, pages, snapshots, events, claims, cross-refs.

Revision ID: 001
Revises:
Create Date: 2026-03-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. sources
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(200), unique=True, nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("homepage_url", sa.String(500), nullable=False),
        sa.Column("base_domain", sa.String(200), nullable=False),
        sa.Column("trust_rating", sa.Float, nullable=False),
        sa.Column("source_role", sa.Text, nullable=False),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("collection_method", sa.String(50), nullable=False, default="html"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 2. pages
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("canonical_url", sa.String(500), unique=True, nullable=False),
        sa.Column("page_type", sa.String(100), nullable=False),
        sa.Column("polling_frequency", sa.String(20), nullable=False, default="daily"),
        sa.Column("priority", sa.Boolean, nullable=False, default=False),
        sa.Column("last_polled_at", sa.DateTime, nullable=True),
        sa.Column("last_changed_at", sa.DateTime, nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 3. snapshots
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("pages.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("fetched_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 4. event_records
    op.create_table(
        "event_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("pages.id"), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("canonical_path", sa.String(500), nullable=False),
        sa.Column("published_date", sa.String(20), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("model_slug", sa.String(200), nullable=True),
        sa.Column("version", sa.String(100), nullable=True),
        sa.Column("observed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "normalized_title",
            "organization",
            "source_type",
            "canonical_path",
            "published_date",
            name="uq_event_composite_key",
        ),
    )

    # 5. claim_records
    op.create_table(
        "claim_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("event_records.id"), nullable=True
        ),
        sa.Column("claim_text", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("page_title", sa.String(500), nullable=True),
        sa.Column("observed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("confidence_tier", sa.String(50), nullable=False),
        sa.Column("confirmation_status", sa.String(50), nullable=False, default="unconfirmed"),
    )

    # 6. cross_references
    op.create_table(
        "cross_references",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "record_a_id", sa.Integer, sa.ForeignKey("event_records.id"), nullable=False
        ),
        sa.Column(
            "record_b_id", sa.Integer, sa.ForeignKey("event_records.id"), nullable=False
        ),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 7. candidate_papers
    op.create_table(
        "candidate_papers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("arxiv_id", sa.String(50), unique=True, nullable=True),
        sa.Column("authors", sa.Text, nullable=True),
        sa.Column("categories", sa.String(200), nullable=True),
        sa.Column("abstract_url", sa.String(500), nullable=True),
        sa.Column("discovered_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("discovered_via", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
    )

    # 8. enriched_papers
    op.create_table(
        "enriched_papers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("arxiv_id", sa.String(50), nullable=True),
        sa.Column("semantic_scholar_id", sa.String(50), nullable=True),
        sa.Column("authors", sa.Text, nullable=True),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.Column("citation_count", sa.Integer, nullable=False, default=0),
        sa.Column("code_url", sa.String(500), nullable=True),
        sa.Column("relevance_tags", sa.Text, nullable=True),
        sa.Column("enriched_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("enriched_papers")
    op.drop_table("candidate_papers")
    op.drop_table("cross_references")
    op.drop_table("claim_records")
    op.drop_table("event_records")
    op.drop_table("snapshots")
    op.drop_table("pages")
    op.drop_table("sources")
