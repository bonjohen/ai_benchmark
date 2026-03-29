"""TargetConfiguration CRUD service with clone support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.target import TargetConfiguration

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _validate_json_field(value, field_name: str, expected_type: type):
    """Validate a JSON field value, accepting strings, the expected type, or None.

    Returns the validated Python object (dict or list).
    Raises ValueError if the value is not valid JSON or not the expected type.
    """
    if value is None:
        return None
    if isinstance(value, expected_type):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"'{field_name}' contains invalid JSON: {exc}") from exc
        if not isinstance(parsed, expected_type):
            raise ValueError(
                f"'{field_name}' must be a {expected_type.__name__}, got {type(parsed).__name__}"
            )
        return parsed
    raise ValueError(
        f"'{field_name}' must be a {expected_type.__name__} or a JSON string, "
        f"got {type(value).__name__}"
    )


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
    inference_params = _validate_json_field(inference_params, "inference_params", dict)
    runtime_options = _validate_json_field(runtime_options, "runtime_options", dict)
    tags = _validate_json_field(tags, "tags", list)

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
    json_field_types = {
        "inference_params": dict,
        "runtime_options": dict,
        "tags": list,
    }
    for key, value in kwargs.items():
        if value is not None and hasattr(t, key):
            if key in json_field_types:
                validated = _validate_json_field(value, key, json_field_types[key])
                setattr(t, key, json.dumps(validated) if validated is not None else None)
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

    # Validate JSON fields in overrides
    if "inference_params" in overrides:
        overrides["inference_params"] = _validate_json_field(
            overrides["inference_params"], "inference_params", dict
        )
    if "runtime_options" in overrides:
        overrides["runtime_options"] = _validate_json_field(
            overrides["runtime_options"], "runtime_options", dict
        )
    if "tags" in overrides:
        overrides["tags"] = _validate_json_field(overrides["tags"], "tags", list)

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
