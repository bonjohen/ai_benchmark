"""Gap Phase G3: Add retry tracking columns to candidate_papers.

Revision ID: 004
Revises: 003
"""

revision = "004"
down_revision = "003"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("candidate_papers", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("candidate_papers", sa.Column("last_retry_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_papers", "last_retry_at")
    op.drop_column("candidate_papers", "retry_count")
