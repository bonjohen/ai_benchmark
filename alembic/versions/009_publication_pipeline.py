"""Publication pipeline: editions, sections, entries, audit log tables.

Revision ID: 009
Revises: 008
"""

revision = "009"
down_revision = "008"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "publication_editions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_date", sa.String(10), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("generation_version", sa.Integer(), server_default="1"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("top_headlines_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("publication_date", name="uq_publication_date"),
    )

    op.create_table(
        "publication_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "edition_id",
            sa.Integer(),
            sa.ForeignKey("publication_editions.id"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("rank", sa.Integer(), server_default="0"),
        sa.Column("item_count", sa.Integer(), server_default="0"),
        sa.Column("generated_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "publication_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "edition_id",
            sa.Integer(),
            sa.ForeignKey("publication_editions.id"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Integer(),
            sa.ForeignKey("publication_sections.id"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), server_default="0"),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("title_generated", sa.Text(), nullable=False),
        sa.Column("title_final", sa.Text(), nullable=False),
        sa.Column("summary_generated", sa.Text(), nullable=False),
        sa.Column("summary_final", sa.Text(), nullable=False),
        sa.Column("why_it_matters_generated", sa.Text(), nullable=True),
        sa.Column("why_it_matters_final", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("score_explanation_json", sa.Text(), nullable=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("event_records.id"),
            nullable=True,
        ),
        sa.Column(
            "paper_id",
            sa.Integer(),
            sa.ForeignKey("enriched_papers.id"),
            nullable=True,
        ),
        sa.Column("benchmark_name", sa.String(200), nullable=True),
        sa.Column("org_slug", sa.String(200), nullable=True),
        sa.Column("model_slug", sa.String(200), nullable=True),
        sa.Column("verification_status", sa.String(50), nullable=True),
        sa.Column("confidence_summary", sa.String(100), nullable=True),
        sa.Column("source_count", sa.Integer(), server_default="0"),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("is_suppressed", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("is_overridden", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("related_entry_ids_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "publication_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "edition_id",
            sa.Integer(),
            sa.ForeignKey("publication_editions.id"),
            nullable=False,
        ),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("publication_entries.id"),
            nullable=True,
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("before_state_json", sa.Text(), nullable=True),
        sa.Column("after_state_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes for common queries
    op.create_index("ix_pub_entries_edition_id", "publication_entries", ["edition_id"])
    op.create_index("ix_pub_entries_event_id", "publication_entries", ["event_id"])
    op.create_index("ix_pub_entries_model_slug", "publication_entries", ["model_slug"])
    op.create_index("ix_pub_audit_edition_id", "publication_audit_log", ["edition_id"])


def downgrade() -> None:
    op.drop_index("ix_pub_audit_edition_id", "publication_audit_log")
    op.drop_index("ix_pub_entries_model_slug", "publication_entries")
    op.drop_index("ix_pub_entries_event_id", "publication_entries")
    op.drop_index("ix_pub_entries_edition_id", "publication_entries")
    op.drop_table("publication_audit_log")
    op.drop_table("publication_entries")
    op.drop_table("publication_sections")
    op.drop_table("publication_editions")
