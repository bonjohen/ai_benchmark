"""Analysis pipeline: analysis_snapshots, analysis_insights tables + indexes.

Revision ID: 008
Revises: 007
"""

revision = "008"
down_revision = "007"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("scope_key", sa.String(200), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("window_start", sa.DateTime(), nullable=True),
        sa.Column("window_end", sa.DateTime(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0"),
        sa.Column("version", sa.Integer(), server_default="1"),
    )

    op.create_table(
        "analysis_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("insight_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("related_event_ids", sa.Text(), nullable=True),
        sa.Column("related_model_slug", sa.String(200), nullable=True),
        sa.Column("related_org", sa.String(200), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            sa.ForeignKey("analysis_snapshots.id"),
            nullable=True,
        ),
    )

    # Indexes on existing tables for analysis query performance
    op.create_index("ix_event_records_model_slug", "event_records", ["model_slug"])
    op.create_index("ix_event_records_organization", "event_records", ["organization"])
    op.create_index("ix_event_records_event_type", "event_records", ["event_type"])
    op.create_index("ix_event_records_observed_at", "event_records", ["observed_at"])
    op.create_index(
        "ix_event_records_benchmark_variant", "event_records", ["benchmark_variant"]
    )
    op.create_index("ix_claim_records_event_id", "claim_records", ["event_id"])
    op.create_index(
        "ix_enriched_papers_citation_count", "enriched_papers", ["citation_count"]
    )


def downgrade() -> None:
    op.drop_index("ix_enriched_papers_citation_count", "enriched_papers")
    op.drop_index("ix_claim_records_event_id", "claim_records")
    op.drop_index("ix_event_records_benchmark_variant", "event_records")
    op.drop_index("ix_event_records_observed_at", "event_records")
    op.drop_index("ix_event_records_event_type", "event_records")
    op.drop_index("ix_event_records_organization", "event_records")
    op.drop_index("ix_event_records_model_slug", "event_records")
    op.drop_table("analysis_insights")
    op.drop_table("analysis_snapshots")
