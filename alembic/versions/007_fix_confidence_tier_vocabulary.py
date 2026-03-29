"""Backfill incorrect confidence_tier value 'independent_report' -> 'high_secondary'.

Revision ID: 007
Revises: 006
"""

revision = "007"
down_revision = "006"

from alembic import op


def upgrade() -> None:
    op.execute(
        "UPDATE claim_records SET confidence_tier = 'high_secondary' "
        "WHERE confidence_tier = 'independent_report'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE claim_records SET confidence_tier = 'independent_report' "
        "WHERE confidence_tier = 'high_secondary'"
    )
