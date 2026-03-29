"""Audit log model — tracks what data was sent where."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_benchmark.models.base import Base


class AuditLogEntry(Base):
    """Records each data transmission event for privacy auditing."""

    __tablename__ = "eval_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    item_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # data_sent, data_received, run_started, run_completed
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_classification: Mapped[str] = mapped_column(
        String(50), nullable=False, default="standard"
    )  # standard, local_only, sensitive
    input_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON extras
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
