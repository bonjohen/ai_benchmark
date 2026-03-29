"""Scorer and ScorerVersion data models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...models.base import Base


class Scorer(Base):
    __tablename__ = "scorers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    scorer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    versions: Mapped[list[ScorerVersion]] = relationship(
        back_populates="scorer", cascade="all, delete-orphan"
    )


class ScorerVersion(Base):
    __tablename__ = "scorer_versions"
    __table_args__ = (UniqueConstraint("scorer_id", "version_number", name="uq_scorer_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scorer_id: Mapped[int] = mapped_column(ForeignKey("scorers.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON: scorer-type-specific parameters
    implementation_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scorer: Mapped[Scorer] = relationship(back_populates="versions")
