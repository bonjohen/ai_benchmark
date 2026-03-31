"""Model registry: model_entities and model_entity_slugs tables.

Revision ID: 010
Revises: 009
"""

revision = "010"
down_revision = "009"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "model_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_slug", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=False),
        sa.Column("model_family", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parameter_count", sa.String(50), nullable=True),
        sa.Column("release_date", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("canonical_slug", name="uq_model_canonical_slug"),
    )

    op.create_table(
        "model_entity_slugs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("model_entities.id"),
            nullable=False,
        ),
        sa.Column("event_slug", sa.String(200), nullable=False),
        sa.Column("source_org", sa.String(200), nullable=False),
        sa.UniqueConstraint("event_slug", "source_org", name="uq_slug_source"),
    )

    op.create_index(
        "ix_model_entity_slugs_event_slug", "model_entity_slugs", ["event_slug"]
    )


def downgrade() -> None:
    op.drop_index("ix_model_entity_slugs_event_slug", "model_entity_slugs")
    op.drop_table("model_entity_slugs")
    op.drop_table("model_entities")
