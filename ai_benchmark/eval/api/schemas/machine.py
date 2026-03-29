"""Machine profile Pydantic schemas."""

from __future__ import annotations


from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class MachineCreate(BaseModel):
    hostname: str
    hardware_class: str
    accelerator_type: str | None = None
    accelerator_count: int | None = None
    accelerator_details: dict | None = None
    cpu_info: str | None = None
    ram_gb: float | None = None
    notes: str | None = None


class MachineUpdate(BaseModel):
    hardware_class: str | None = None
    accelerator_type: str | None = None
    accelerator_count: int | None = None
    accelerator_details: dict | None = None
    cpu_info: str | None = None
    ram_gb: float | None = None
    notes: str | None = None


class MachineResponse(BaseModel):
    id: int
    hostname: str
    hardware_class: str
    accelerator_type: str | None
    accelerator_count: int | None
    accelerator_details: dict | None
    cpu_info: str | None
    ram_gb: float | None
    notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class SnapshotCaptureRequest(BaseModel):
    runtime_info: dict | None = None


class MachineSnapshotResponse(BaseModel):
    id: int
    machine_profile_id: int
    snapshot_data: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
