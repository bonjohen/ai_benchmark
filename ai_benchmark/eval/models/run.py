"""RunGroup, Run, RunItemResult, and RunAggregateMetric data models."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...models.base import Base


class RunGroup(Base):
    __tablename__ = "run_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # batch | matrix | scheduled
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    runs: Mapped[list[Run]] = relationship(back_populates="run_group")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_group_id: Mapped[int | None] = mapped_column(ForeignKey("run_groups.id"), nullable=True)
    evaluation_version_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_versions.id"), nullable=False
    )
    target_config_id: Mapped[int] = mapped_column(
        ForeignKey("target_configurations.id"), nullable=False
    )
    machine_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("machine_snapshots.id"), nullable=True
    )
    dataset_version_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False
    )

    scorer_version_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    runner_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: runner version + metadata at execution time
    requested_config: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: full target config snapshot as requested
    effective_config: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: what the runner actually used (may differ from requested)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_local_only: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scoring_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    run_group: Mapped[RunGroup | None] = relationship(back_populates="runs")
    evaluation_version: Mapped[EvaluationVersion] = relationship(  # noqa: F821
        back_populates="runs"
    )
    target_config: Mapped[TargetConfiguration] = relationship(  # noqa: F821
        back_populates="runs"
    )
    machine_snapshot: Mapped[MachineSnapshot | None] = relationship()  # noqa: F821
    item_results: Mapped[list[RunItemResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    aggregate_metrics: Mapped[list[RunAggregateMetric]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[Artifact]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan"
    )


class RunItemResult(Base):
    __tablename__ = "run_item_results"
    __table_args__ = (
        Index("ix_run_item_results_run_index", "run_id", "item_index"),
        Index("ix_run_item_results_run_pass", "run_id", "overall_pass"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)

    input_sent: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    scorer_results: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON: list of {scorer_version_id, score, pass, details}
    overall_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    trace_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped[Run] = relationship(back_populates="item_results")
    test_case: Mapped[TestCase] = relationship()  # noqa: F821


class RunAggregateMetric(Base):
    __tablename__ = "run_aggregate_metrics"
    __table_args__ = (UniqueConstraint("run_id", "metric_name", name="uq_run_metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    run: Mapped[Run] = relationship(back_populates="aggregate_metrics")
