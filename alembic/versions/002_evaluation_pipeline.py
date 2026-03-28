"""Create evaluation pipeline tables.

Revision ID: 002
Revises:
Create Date: 2026-03-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. datasets
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_archived", sa.Boolean, default=False),
    )

    # 2. dataset_versions
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False, default=0),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )

    # 3. test_cases
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_version_id",
            sa.Integer,
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("item_index", sa.Integer, nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("expected_output", sa.Text, nullable=True),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column("metadata", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_test_cases_version_index", "test_cases", ["dataset_version_id", "item_index"]
    )

    # 4. scorers
    op.create_table(
        "scorers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("scorer_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_archived", sa.Boolean, default=False),
    )

    # 5. scorer_versions
    op.create_table(
        "scorer_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scorer_id", sa.Integer, sa.ForeignKey("scorers.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("config", sa.Text, nullable=False),
        sa.Column("implementation_ref", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("scorer_id", "version_number", name="uq_scorer_version"),
    )

    # 6. evaluation_definitions
    op.create_table(
        "evaluation_definitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("suite_name", sa.String(200), nullable=True),
        sa.Column("execution_mode", sa.String(50), nullable=False, default="sequential"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("is_archived", sa.Boolean, default=False),
    )

    # 7. evaluation_versions
    op.create_table(
        "evaluation_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "evaluation_id",
            sa.Integer,
            sa.ForeignKey("evaluation_definitions.id"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column(
            "dataset_version_id",
            sa.Integer,
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("scorer_config", sa.Text, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=True),
        sa.Column("preprocessing", sa.Text, nullable=True),
        sa.Column("pass_criteria", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "evaluation_id", "version_number", name="uq_evaluation_version"
        ),
    )

    # 8. machine_profiles
    op.create_table(
        "machine_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("hostname", sa.String(200), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("hardware_class", sa.String(100), nullable=False),
        sa.Column("cpu_description", sa.String(200), nullable=True),
        sa.Column("gpu_description", sa.String(200), nullable=True),
        sa.Column("accelerator_details", sa.Text, nullable=True),
        sa.Column("ram_gb", sa.Integer, nullable=True),
        sa.Column("storage_summary", sa.String(200), nullable=True),
        sa.Column("os_description", sa.String(200), nullable=True),
        sa.Column("runtime_availability", sa.Text, nullable=True),
        sa.Column("capacity_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # 9. machine_snapshots
    op.create_table(
        "machine_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "machine_profile_id",
            sa.Integer,
            sa.ForeignKey("machine_profiles.id"),
            nullable=False,
        ),
        sa.Column("snapshot_data", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 10. target_configurations
    op.create_table(
        "target_configurations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model_family", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("endpoint_url", sa.String(500), nullable=True),
        sa.Column(
            "machine_profile_id",
            sa.Integer,
            sa.ForeignKey("machine_profiles.id"),
            nullable=True,
        ),
        sa.Column("runtime_backend", sa.String(100), nullable=True),
        sa.Column("prompt_wrapper", sa.Text, nullable=True),
        sa.Column("inference_params", sa.Text, nullable=False),
        sa.Column("runtime_options", sa.Text, nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("is_archived", sa.Boolean, default=False),
    )

    # 11. run_groups
    op.create_table(
        "run_groups",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("execution_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 12. runs
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_group_id", sa.Integer, sa.ForeignKey("run_groups.id"), nullable=True),
        sa.Column(
            "evaluation_version_id",
            sa.Integer,
            sa.ForeignKey("evaluation_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "target_config_id",
            sa.Integer,
            sa.ForeignKey("target_configurations.id"),
            nullable=False,
        ),
        sa.Column(
            "machine_snapshot_id",
            sa.Integer,
            sa.ForeignKey("machine_snapshots.id"),
            nullable=True,
        ),
        sa.Column(
            "dataset_version_id",
            sa.Integer,
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, default="queued"),
        sa.Column("trigger_type", sa.String(30), nullable=False, default="manual"),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("scoring_started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("total_items", sa.Integer, nullable=False, default=0),
        sa.Column("completed_items", sa.Integer, nullable=False, default=0),
        sa.Column("failed_items", sa.Integer, nullable=False, default=0),
        sa.Column("skipped_items", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # 13. run_item_results
    op.create_table(
        "run_item_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("test_case_id", sa.Integer, sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("item_index", sa.Integer, nullable=False),
        sa.Column("input_sent", sa.Text, nullable=False),
        sa.Column("raw_output", sa.Text, nullable=True),
        sa.Column("normalized_output", sa.Text, nullable=True),
        sa.Column("scorer_results", sa.Text, nullable=False),
        sa.Column("overall_pass", sa.Boolean, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("cost_estimate_usd", sa.Float, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("trace_id", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_run_item_results_run_index", "run_item_results", ["run_id", "item_index"]
    )
    op.create_index(
        "ix_run_item_results_run_pass", "run_item_results", ["run_id", "overall_pass"]
    )

    # 14. run_aggregate_metrics
    op.create_table(
        "run_aggregate_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("metric_name", sa.String(200), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("metric_metadata", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "metric_name", name="uq_run_metric"),
    )

    # 15. artifacts
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("run_aggregate_metrics")
    op.drop_index("ix_run_item_results_run_pass", table_name="run_item_results")
    op.drop_index("ix_run_item_results_run_index", table_name="run_item_results")
    op.drop_table("run_item_results")
    op.drop_table("runs")
    op.drop_table("run_groups")
    op.drop_table("target_configurations")
    op.drop_table("machine_snapshots")
    op.drop_table("machine_profiles")
    op.drop_table("evaluation_versions")
    op.drop_table("evaluation_definitions")
    op.drop_table("scorer_versions")
    op.drop_table("scorers")
    op.drop_index("ix_test_cases_version_index", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
