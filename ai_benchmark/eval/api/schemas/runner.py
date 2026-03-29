"""Runner profile Pydantic schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class RunnerCreate(BaseModel):
    name: str
    runner_class: str
    display_name: str | None = None
    version: str | None = None
    supported_machine_classes: list[str] | None = None
    supported_model_families: list[str] | None = None
    parameter_surface: dict | None = None
    default_endpoint_url: str | None = None
    notes: str | None = None


class RunnerUpdate(BaseModel):
    display_name: str | None = None
    version: str | None = None
    supported_machine_classes: list[str] | None = None
    supported_model_families: list[str] | None = None
    parameter_surface: dict | None = None
    default_endpoint_url: str | None = None
    notes: str | None = None
    is_archived: bool | None = None


class RunnerResponse(BaseModel):
    id: int
    name: str
    runner_class: str
    display_name: str | None
    version: str | None
    supported_machine_classes: list[str] | None
    supported_model_families: list[str] | None
    parameter_surface: dict | None
    default_endpoint_url: str | None
    notes: str | None
    is_archived: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}
