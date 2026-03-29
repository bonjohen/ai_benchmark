"""Gap Phase G1: Schema extensions for benchmark_variant, snapshot_id FK, model_slug in dedup key.

Revision ID: 003
Revises: 002
"""

revision = "003"
down_revision = "002"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # EventRecord: add benchmark_variant and evaluation_conditions
    op.add_column("event_records", sa.Column("benchmark_variant", sa.String(100), nullable=True))
    op.add_column("event_records", sa.Column("evaluation_conditions", sa.Text(), nullable=True))

    # ClaimRecord: add snapshot_id FK
    op.add_column(
        "claim_records",
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("snapshots.id"), nullable=True),
    )

    # Update composite unique constraint to include model_slug
    op.drop_constraint("uq_event_composite_key", "event_records", type_="unique")
    op.create_unique_constraint(
        "uq_event_composite_key",
        "event_records",
        ["normalized_title", "organization", "source_type", "canonical_path", "published_date", "model_slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_event_composite_key", "event_records", type_="unique")
    op.create_unique_constraint(
        "uq_event_composite_key",
        "event_records",
        ["normalized_title", "organization", "source_type", "canonical_path", "published_date"],
    )
    op.drop_column("claim_records", "snapshot_id")
    op.drop_column("event_records", "evaluation_conditions")
    op.drop_column("event_records", "benchmark_variant")
