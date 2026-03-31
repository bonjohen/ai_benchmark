"""Analysis pipeline ORM models: snapshots, insights, and model registry."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class ModelEntity(Base):
    """Curated model identity in the model registry."""

    __tablename__ = "model_entities"
    __table_args__ = (UniqueConstraint("canonical_slug", name="uq_model_canonical_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_slug: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(200))
    model_family: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameter_count: Mapped[str | None] = mapped_column(String(50), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    slugs: Mapped[list[ModelEntitySlug]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class ModelEntitySlug(Base):
    """Maps a raw event model_slug to a curated ModelEntity."""

    __tablename__ = "model_entity_slugs"
    __table_args__ = (
        Index("ix_model_entity_slugs_event_slug", "event_slug"),
        UniqueConstraint("event_slug", "source_org", name="uq_slug_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("model_entities.id"))
    event_slug: Mapped[str] = mapped_column(String(200))
    source_org: Mapped[str] = mapped_column(String(200))

    entity: Mapped[ModelEntity] = relationship(back_populates="slugs")
