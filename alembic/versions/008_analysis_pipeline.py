"""Add performance indexes to core ETL tables.

Revision ID: 008
Revises: 007
"""

revision = "008"
down_revision = "007"

from alembic import op


def upgrade() -> None:
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
