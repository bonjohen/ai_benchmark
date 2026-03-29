"""Research paper models for the triage pipeline."""

from __future__ import annotations


from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from datetime import datetime  # noqa: TC003

from .base import Base


class CandidatePaper(Base):
    __tablename__ = "candidate_papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    arxiv_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[str | None] = mapped_column(String(200), nullable=True)
    abstract_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    discovered_via: Mapped[str] = mapped_column(String(50))  # arxiv, hf_papers
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, enriched, promoted, rejected
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EnrichedPaper(Base):
    __tablename__ = "enriched_papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    arxiv_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    code_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    relevance_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
