"""Discovery automation models: follow-up tasks for new model slugs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_slug: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(
        String(50)
    )  # pricing_search, release_notes_search, system_card_search, benchmark_coverage_search
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
