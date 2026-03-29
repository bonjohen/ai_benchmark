"""Machine profile routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...services import machine_service
from ..app import get_session
from ..schemas.machine import (
    MachineCreate,
    MachineResponse,
    MachineSnapshotResponse,
    MachineUpdate,
    SnapshotCaptureRequest,
)

router = APIRouter()


@router.get("", response_model=list[MachineResponse])
async def list_machines(
    hardware_class: str | None = None,
    hostname: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    machines = await machine_service.list_profiles(
        session, hardware_class=hardware_class, hostname=hostname,
    )
    return [_machine_to_dict(m) for m in machines]


@router.post("", response_model=MachineResponse, status_code=201)
async def create_machine(
    body: MachineCreate,
    session: AsyncSession = Depends(get_session),
):
    m = await machine_service.create_profile(
        session,
        hostname=body.hostname,
        hardware_class=body.hardware_class,
        accelerator_details=body.accelerator_details,
        ram_gb=body.ram_gb,
    )
    result = _machine_to_dict(m)

    await session.commit()

    return result


@router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(
    machine_id: int,
    session: AsyncSession = Depends(get_session),
):
    m = await machine_service.get_profile(session, machine_id)
    if m is None:
        raise HTTPException(404, "Machine not found")
    return _machine_to_dict(m)


@router.put("/{machine_id}", response_model=MachineResponse)
async def update_machine(
    machine_id: int,
    body: MachineUpdate,
    session: AsyncSession = Depends(get_session),
):
    kwargs = body.model_dump(exclude_none=True)
    if "accelerator_details" in kwargs and isinstance(kwargs["accelerator_details"], dict):
        kwargs["accelerator_details"] = json.dumps(kwargs["accelerator_details"])
    m = await machine_service.update_profile(session, machine_id, **kwargs)
    if m is None:
        raise HTTPException(404, "Machine not found")
    result = _machine_to_dict(m)

    await session.commit()

    return result


@router.post(
    "/{machine_id}/snapshot",
    response_model=MachineSnapshotResponse,
    status_code=201,
)
async def capture_snapshot(
    machine_id: int,
    body: SnapshotCaptureRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    snap = await machine_service.capture_snapshot(session, machine_id)
    result = _snapshot_to_dict(snap)

    await session.commit()

    return result


def _machine_to_dict(m) -> dict:
    return {
        "id": m.id,
        "hostname": m.hostname,
        "hardware_class": m.hardware_class,
        "accelerator_type": getattr(m, "accelerator_type", None),
        "accelerator_count": getattr(m, "accelerator_count", None),
        "accelerator_details": (
            json.loads(m.accelerator_details) if getattr(m, "accelerator_details", None) else None
        ),
        "cpu_info": getattr(m, "cpu_description", None),
        "ram_gb": getattr(m, "ram_gb", None),
        "notes": getattr(m, "capacity_notes", None),
        "created_at": m.created_at,
    }


def _snapshot_to_dict(s) -> dict:
    return {
        "id": s.id,
        "machine_profile_id": s.machine_profile_id,
        "snapshot_data": json.loads(s.snapshot_data) if s.snapshot_data else None,
        "created_at": s.created_at,
    }
