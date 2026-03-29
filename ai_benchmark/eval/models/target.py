"""TargetConfiguration data model."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...models.base import Base


class TargetConfiguration(Base):
    __tablename__ = "target_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    machine_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("machine_profiles.id"), nullable=True
    )
    runtime_backend: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_wrapper: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_params: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    runtime_options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    machine_profile: Mapped[MachineProfile | None] = relationship(  # noqa: F821
        back_populates="target_configs"
    )
    runs: Mapped[list[Run]] = relationship(back_populates="target_config")  # noqa: F821
