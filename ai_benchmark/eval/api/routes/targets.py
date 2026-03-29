"""Target configuration routes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ...services import target_service
from ..app import get_session
from ..schemas.target import TargetClone, TargetCreate, TargetResponse, TargetUpdate
from ..serializers import target_to_dict as _target_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[TargetResponse])
async def list_targets(
    model_name: str | None = None,
    provider: str | None = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
):
    targets = await target_service.list_targets(
        session,
        model_name=model_name,
        provider=provider,
        include_archived=include_archived,
    )
    return [_target_to_dict(t) for t in targets]


@router.post("", response_model=TargetResponse, status_code=201)
async def create_target(
    body: TargetCreate,
    session: AsyncSession = Depends(get_session),
):
    t = await target_service.create_target(
        session,
        name=body.name,
        model_name=body.model_name,
        provider=body.provider,
        inference_params=body.inference_params,
        model_family=body.model_family,
        endpoint_url=body.endpoint_url,
        machine_profile_id=body.machine_profile_id,
        runtime_backend=body.runtime_backend,
        prompt_wrapper=body.prompt_wrapper,
        runtime_options=body.runtime_options,
        tags=body.tags,
        notes=body.notes,
    )
    result = _target_to_dict(t)

    await session.commit()

    return result


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: int,
    session: AsyncSession = Depends(get_session),
):
    t = await target_service.get_target(session, target_id)
    if t is None:
        raise HTTPException(404, "Target not found")
    return _target_to_dict(t)


@router.put("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: int,
    body: TargetUpdate,
    session: AsyncSession = Depends(get_session),
):
    kwargs = body.model_dump(exclude_none=True)
    # JSON-serialize dict fields
    for field in ("inference_params", "runtime_options", "tags"):
        if field in kwargs and isinstance(kwargs[field], (dict, list)):
            kwargs[field] = json.dumps(kwargs[field])
    t = await target_service.update_target(session, target_id, **kwargs)
    if t is None:
        raise HTTPException(404, "Target not found")
    result = _target_to_dict(t)

    await session.commit()

    return result


@router.post("/{target_id}/clone", response_model=TargetResponse, status_code=201)
async def clone_target(
    target_id: int,
    body: TargetClone,
    session: AsyncSession = Depends(get_session),
):
    t = await target_service.clone_target(
        session,
        target_id,
        new_name=body.new_name,
        overrides=body.overrides,
    )
    result = _target_to_dict(t)

    await session.commit()

    return result
