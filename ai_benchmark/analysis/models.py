"""Analysis pipeline ORM models: snapshots and insights."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..models.base import Base


class AnalysisSnapshot(Base):
    """Persisted analysis result for caching and historical comparison."""

    __tablename__ = "analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(50))
    scope_key: Mapped[str] = mapped_column(String(200))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[str] = mapped_column(Text)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AnalysisInsight(Base):
    """Individual flagged finding from anomaly detection."""

    __tablename__ = "analysis_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    insight_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    related_event_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_model_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    related_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_snapshots.id"), nullable=True
    )
