"""Publication pipeline ORM models: editions, sections, entries, and audit log."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models.base import Base


class PublicationEdition(Base):
    """One daily publication edition."""

    __tablename__ = "publication_editions"
    __table_args__ = (UniqueConstraint("publication_date", name="uq_publication_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft, published, frozen, regeneration_available
    generation_version: Mapped[int] = mapped_column(Integer, default=1)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_headlines_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    sections: Mapped[list[PublicationSection]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )
    entries: Mapped[list[PublicationEntry]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[PublicationAuditLog]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )


class PublicationSection(Base):
    """One section within a daily edition."""

    __tablename__ = "publication_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("publication_editions.id"))
    section_key: Mapped[str] = mapped_column(String(50))  # benchmark_movers, announcements, etc.
    title: Mapped[str] = mapped_column(String(200))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    edition: Mapped[PublicationEdition] = relationship(back_populates="sections")
    entries: Mapped[list[PublicationEntry]] = relationship(back_populates="section")


class PublicationEntry(Base):
    """One entry within a publication section."""

    __tablename__ = "publication_entries"
    __table_args__ = (
        Index("ix_pub_entries_edition_id", "edition_id"),
        Index("ix_pub_entries_event_id", "event_id"),
        Index("ix_pub_entries_model_slug", "model_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("publication_editions.id"))
    section_id: Mapped[int] = mapped_column(ForeignKey("publication_sections.id"))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    entry_type: Mapped[str] = mapped_column(String(50))  # benchmark_result, model_release, etc.

    title_generated: Mapped[str] = mapped_column(Text)
    title_final: Mapped[str] = mapped_column(Text)
    summary_generated: Mapped[str] = mapped_column(Text)
    summary_final: Mapped[str] = mapped_column(Text)
    why_it_matters_generated: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters_final: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active, suppressed
    score: Mapped[float] = mapped_column(default=0.0)
    score_explanation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_id: Mapped[int | None] = mapped_column(ForeignKey("event_records.id"), nullable=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("enriched_papers.id"), nullable=True)
    benchmark_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    org_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_summary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0)

    is_pinned: Mapped[bool] = mapped_column(default=False)
    is_suppressed: Mapped[bool] = mapped_column(default=False)
    is_overridden: Mapped[bool] = mapped_column(default=False)

    related_entry_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    edition: Mapped[PublicationEdition] = relationship(back_populates="entries")
    section: Mapped[PublicationSection] = relationship(back_populates="entries")


class PublicationAuditLog(Base):
    """Audit trail for editorial actions on editions and entries."""

    __tablename__ = "publication_audit_log"
    __table_args__ = (Index("ix_pub_audit_edition_id", "edition_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("publication_editions.id"))
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("publication_entries.id"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(50))  # pin, suppress, override, freeze, etc.
    actor: Mapped[str] = mapped_column(String(200))
    before_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    edition: Mapped[PublicationEdition] = relationship(back_populates="audit_logs")
