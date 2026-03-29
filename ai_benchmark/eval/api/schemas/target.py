"""Target configuration Pydantic schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class TargetCreate(BaseModel):
    name: str
    model_name: str
    model_family: str | None = None
    provider: str
    endpoint_url: str | None = None
    machine_profile_id: int | None = None
    runtime_backend: str | None = None
    prompt_wrapper: str | None = None
    inference_params: dict = {}
    runtime_options: dict | None = None
    tags: list[str] | None = None
    notes: str | None = None


class TargetUpdate(BaseModel):
    model_name: str | None = None
    model_family: str | None = None
    provider: str | None = None
    endpoint_url: str | None = None
    prompt_wrapper: str | None = None
    inference_params: dict | None = None
    runtime_options: dict | None = None
    tags: list[str] | None = None
    notes: str | None = None
    is_archived: bool | None = None


class TargetClone(BaseModel):
    new_name: str
    overrides: dict = {}


class TargetResponse(BaseModel):
    id: int
    name: str
    model_name: str
    model_family: str | None
    provider: str
    endpoint_url: str | None
    machine_profile_id: int | None
    runtime_backend: str | None
    prompt_wrapper: str | None
    inference_params: dict | None
    runtime_options: dict | None
    tags: list | None
    notes: str | None
    is_archived: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
