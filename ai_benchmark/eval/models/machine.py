"""MachineProfile and MachineSnapshot data models."""

from __future__ import annotations


from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datetime import datetime  # noqa: TC003

from ...models.base import Base


class MachineProfile(Base):
    __tablename__ = "machine_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hardware_class: Mapped[str] = mapped_column(String(100), nullable=False)
    cpu_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gpu_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accelerator_details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ram_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    os_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    runtime_availability: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    capacity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    snapshots: Mapped[list[MachineSnapshot]] = relationship(
        back_populates="machine_profile", cascade="all, delete-orphan"
    )
    target_configs: Mapped[list[TargetConfiguration]] = relationship(  # noqa: F821
        back_populates="machine_profile"
    )


class MachineSnapshot(Base):
    __tablename__ = "machine_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_profile_id: Mapped[int] = mapped_column(
        ForeignKey("machine_profiles.id"), nullable=False
    )
    snapshot_data: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON: full profile copy + runtime metadata
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    machine_profile: Mapped[MachineProfile] = relationship(back_populates="snapshots")
