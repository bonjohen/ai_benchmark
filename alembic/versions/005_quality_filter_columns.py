"""Gap Phase G5: Add times_polled column to pages.

Revision ID: 005
Revises: 004
"""

revision = "005"
down_revision = "004"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("pages", sa.Column("times_polled", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("pages", "times_polled")
