"""MachineProfile and MachineSnapshot CRUD service."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.machine import MachineProfile, MachineSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_profile(
    session: AsyncSession,
    *,
    hostname: str,
    hardware_class: str,
    display_name: str | None = None,
    cpu_description: str | None = None,
    gpu_description: str | None = None,
    accelerator_details: dict | None = None,
    ram_gb: int | None = None,
    storage_summary: str | None = None,
    os_description: str | None = None,
    runtime_availability: list[str] | None = None,
    capacity_notes: str | None = None,
) -> MachineProfile:
    m = MachineProfile(
        hostname=hostname,
        hardware_class=hardware_class,
        display_name=display_name,
        cpu_description=cpu_description,
        gpu_description=gpu_description,
        accelerator_details=json.dumps(accelerator_details) if accelerator_details else None,
        ram_gb=ram_gb,
        storage_summary=storage_summary,
        os_description=os_description,
        runtime_availability=json.dumps(runtime_availability) if runtime_availability else None,
        capacity_notes=capacity_notes,
    )
    session.add(m)
    await session.flush()
    return m


async def list_profiles(
    session: AsyncSession,
    *,
    hardware_class: str | None = None,
    hostname: str | None = None,
) -> list[MachineProfile]:
    stmt = select(MachineProfile)
    if hardware_class:
        stmt = stmt.where(MachineProfile.hardware_class == hardware_class)
    if hostname:
        stmt = stmt.where(MachineProfile.hostname.ilike(f"%{hostname}%"))
    stmt = stmt.order_by(MachineProfile.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_profile(session: AsyncSession, profile_id: int) -> MachineProfile | None:
    return await session.get(MachineProfile, profile_id)


async def update_profile(
    session: AsyncSession,
    profile_id: int,
    **kwargs,
) -> MachineProfile | None:
    m = await session.get(MachineProfile, profile_id)
    if m is None:
        return None
    json_fields = {"accelerator_details", "runtime_availability"}
    for key, value in kwargs.items():
        if value is not None and hasattr(m, key):
            if key in json_fields and isinstance(value, (dict, list)):
                setattr(m, key, json.dumps(value))
            else:
                setattr(m, key, value)
    await session.flush()
    await session.refresh(m)
    return m


async def capture_snapshot(
    session: AsyncSession,
    profile_id: int,
    *,
    runtime_version: str | None = None,
    model_server_version: str | None = None,
    env_vars: dict | None = None,
    tuning_values: dict | None = None,
) -> MachineSnapshot:
    """Capture current machine profile state as an immutable snapshot."""
    m = await session.get(MachineProfile, profile_id)
    if m is None:
        raise ValueError(f"MachineProfile {profile_id} not found")

    snapshot_data = {
        "hostname": m.hostname,
        "display_name": m.display_name,
        "hardware_class": m.hardware_class,
        "cpu_description": m.cpu_description,
        "gpu_description": m.gpu_description,
        "accelerator_details": json.loads(m.accelerator_details) if m.accelerator_details else None,
        "ram_gb": m.ram_gb,
        "storage_summary": m.storage_summary,
        "os_description": m.os_description,
        "runtime_availability": json.loads(m.runtime_availability)
        if m.runtime_availability
        else None,
        "runtime_version": runtime_version,
        "model_server_version": model_server_version,
        "env_vars": env_vars,
        "tuning_values": tuning_values,
    }

    snap = MachineSnapshot(
        machine_profile_id=profile_id,
        snapshot_data=json.dumps(snapshot_data),
    )
    session.add(snap)
    await session.flush()
    return snap
