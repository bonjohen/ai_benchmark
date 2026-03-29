"""TargetConfiguration CRUD service with clone support."""

from __future__ import annotations

import json

from sqlalchemy import select

from ..models.target import TargetConfiguration
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_target(
    session: AsyncSession,
    *,
    name: str,
    model_name: str,
    provider: str,
    inference_params: dict,
    model_family: str | None = None,
    endpoint_url: str | None = None,
    machine_profile_id: int | None = None,
    runtime_backend: str | None = None,
    prompt_wrapper: str | None = None,
    runtime_options: dict | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> TargetConfiguration:
    t = TargetConfiguration(
        name=name,
        model_name=model_name,
        model_family=model_family,
        provider=provider,
        endpoint_url=endpoint_url,
        machine_profile_id=machine_profile_id,
        runtime_backend=runtime_backend,
        prompt_wrapper=prompt_wrapper,
        inference_params=json.dumps(inference_params),
        runtime_options=json.dumps(runtime_options) if runtime_options else None,
        tags=json.dumps(tags) if tags else None,
        notes=notes,
    )
    session.add(t)
    await session.flush()
    return t


async def list_targets(
    session: AsyncSession,
    *,
    model_name: str | None = None,
    provider: str | None = None,
    machine_profile_id: int | None = None,
    hardware_class: str | None = None,
    include_archived: bool = False,
) -> list[TargetConfiguration]:
    stmt = select(TargetConfiguration)
    if not include_archived:
        stmt = stmt.where(TargetConfiguration.is_archived == False)  # noqa: E712
    if model_name:
        stmt = stmt.where(TargetConfiguration.model_name.ilike(f"%{model_name}%"))
    if provider:
        stmt = stmt.where(TargetConfiguration.provider == provider)
    if machine_profile_id:
        stmt = stmt.where(TargetConfiguration.machine_profile_id == machine_profile_id)
    stmt = stmt.order_by(TargetConfiguration.created_at.desc())
    result = await session.execute(stmt)
    targets = list(result.scalars().all())

    # Post-query filter for hardware_class (requires join with machine_profile)
    if hardware_class:
        from ..models.machine import MachineProfile

        machine_ids_stmt = select(MachineProfile.id).where(
            MachineProfile.hardware_class == hardware_class
        )
        machine_result = await session.execute(machine_ids_stmt)
        valid_ids = set(machine_result.scalars().all())
        targets = [t for t in targets if t.machine_profile_id in valid_ids]

    return targets


async def get_target(session: AsyncSession, target_id: int) -> TargetConfiguration | None:
    return await session.get(TargetConfiguration, target_id)


async def update_target(
    session: AsyncSession,
    target_id: int,
    **kwargs,
) -> TargetConfiguration | None:
    t = await session.get(TargetConfiguration, target_id)
    if t is None:
        return None
    json_fields = {"inference_params", "runtime_options", "tags"}
    for key, value in kwargs.items():
        if value is not None and hasattr(t, key):
            if key in json_fields and isinstance(value, (dict, list)):
                setattr(t, key, json.dumps(value))
            else:
                setattr(t, key, value)
    await session.flush()
    await session.refresh(t)
    return t


async def clone_target(
    session: AsyncSession,
    target_id: int,
    *,
    new_name: str,
    overrides: dict | None = None,
) -> TargetConfiguration:
    """Clone a target configuration, applying optional field overrides."""
    source = await session.get(TargetConfiguration, target_id)
    if source is None:
        raise ValueError(f"TargetConfiguration {target_id} not found")

    overrides = overrides or {}
    t = TargetConfiguration(
        name=new_name,
        model_name=overrides.get("model_name", source.model_name),
        model_family=overrides.get("model_family", source.model_family),
        provider=overrides.get("provider", source.provider),
        endpoint_url=overrides.get("endpoint_url", source.endpoint_url),
        machine_profile_id=overrides.get("machine_profile_id", source.machine_profile_id),
        runtime_backend=overrides.get("runtime_backend", source.runtime_backend),
        prompt_wrapper=overrides.get("prompt_wrapper", source.prompt_wrapper),
        inference_params=json.dumps(overrides["inference_params"])
        if "inference_params" in overrides
        else source.inference_params,
        runtime_options=json.dumps(overrides["runtime_options"])
        if "runtime_options" in overrides
        else source.runtime_options,
        tags=json.dumps(overrides["tags"]) if "tags" in overrides else source.tags,
        notes=overrides.get("notes", source.notes),
    )
    session.add(t)
    await session.flush()
    return t
