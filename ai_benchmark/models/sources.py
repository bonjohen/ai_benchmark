"""Source, Page, and Snapshot data models."""

from __future__ import annotations


from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datetime import datetime  # noqa: TC003

from .base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(100))
    organization: Mapped[str] = mapped_column(String(200))
    homepage_url: Mapped[str] = mapped_column(String(500))
    base_domain: Mapped[str] = mapped_column(String(200))
    trust_rating: Mapped[float] = mapped_column(Float)
    source_role: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(50))
    collection_method: Mapped[str] = mapped_column(String(50), default="html")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pages: Mapped[list[Page]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    canonical_url: Mapped[str] = mapped_column(String(500), unique=True)
    page_type: Mapped[str] = mapped_column(String(100))
    polling_frequency: Mapped[str] = mapped_column(String(20), default="daily")
    priority: Mapped[bool] = mapped_column(default=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_polled: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="pages")
    snapshots: Mapped[list[Snapshot]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    page: Mapped[Page] = relationship(back_populates="snapshots")
