"""EventRecord, ClaimRecord, and CrossReference data models."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .sources import Snapshot  # noqa: TC001


class EventRecord(Base):
    __tablename__ = "event_records"
    __table_args__ = (
        UniqueConstraint(
            "normalized_title",
            "organization",
            "source_type",
            "canonical_path",
            "published_date",
            "model_slug",
            name="uq_event_composite_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id"), nullable=True)

    title: Mapped[str] = mapped_column(Text)
    normalized_title: Mapped[str] = mapped_column(String(500))
    organization: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(100))
    canonical_path: Mapped[str] = mapped_column(String(500))
    published_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    event_type: Mapped[str] = mapped_column(String(50))  # model_release, pricing_change, etc.
    model_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    benchmark_variant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evaluation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    claims: Mapped[list[ClaimRecord]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class ClaimRecord(Base):
    __tablename__ = "claim_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event_records.id"), nullable=True)

    claim_text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(100))
    source_name: Mapped[str] = mapped_column(String(200))
    page_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    confidence_tier: Mapped[str] = mapped_column(
        String(50)
    )  # official_self_report, benchmark_owner_report, etc.

    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id"), nullable=True)

    confirmation_status: Mapped[str] = mapped_column(
        String(50), default="unconfirmed"
    )  # unconfirmed, confirmed, conflicted

    event: Mapped[EventRecord | None] = relationship(back_populates="claims")
    snapshot: Mapped[Snapshot | None] = relationship()


class CrossReference(Base):
    __tablename__ = "cross_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_a_id: Mapped[int] = mapped_column(ForeignKey("event_records.id"))
    record_b_id: Mapped[int] = mapped_column(ForeignKey("event_records.id"))
    relationship_type: Mapped[str] = mapped_column(
        String(50)
    )  # confirms, supplements, conflicts_with, cites
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    record_a: Mapped[EventRecord] = relationship(foreign_keys=[record_a_id])
    record_b: Mapped[EventRecord] = relationship(foreign_keys=[record_b_id])
