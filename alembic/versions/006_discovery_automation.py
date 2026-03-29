"""Gap Phase G6: Create follow_up_tasks table for discovery automation.

Revision ID: 006
Revises: 005
"""

revision = "006"
down_revision = "005"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "follow_up_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_slug", sa.String(200), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("follow_up_tasks")
