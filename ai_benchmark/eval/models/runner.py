"""RunnerProfile data model — first-class runner registry."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ...models.base import Base


class RunnerProfile(Base):
    __tablename__ = "runner_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    runner_class: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # ollama, lmstudio, llamacpp, mlx, vllm, sglang, tensorrt, openvino
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supported_machine_classes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    supported_model_families: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    parameter_surface: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: known parameter fields
    default_endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
