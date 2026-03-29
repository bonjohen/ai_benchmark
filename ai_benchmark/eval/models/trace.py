"""TraceReference and Annotation data models."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ...models.base import Base


class TraceReference(Base):
    __tablename__ = "trace_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_item_result_id: Mapped[int] = mapped_column(
        ForeignKey("run_item_results.id"), nullable=False
    )
    trace_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # token_usage, latency_breakdown, retry_log, cost_estimate
    trace_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # run, run_group, run_item_result
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # baseline, regression, preferred, obsolete, unstable
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
