"""Runner profile routes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ...services import runner_service
from ..app import get_session
from ..schemas.runner import RunnerCreate, RunnerResponse, RunnerUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[RunnerResponse])
async def list_runners(
    runner_class: str | None = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    runners = await runner_service.list_runners(
        session, runner_class=runner_class, include_archived=include_archived
    )
    return [_runner_to_dict(r) for r in runners]


@router.post("", response_model=RunnerResponse, status_code=201)
async def create_runner(
    body: RunnerCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    kwargs = body.model_dump(exclude_none=True)
    if "supported_machine_classes" in kwargs:
        kwargs["supported_machine_classes"] = json.dumps(kwargs["supported_machine_classes"])
    if "supported_model_families" in kwargs:
        kwargs["supported_model_families"] = json.dumps(kwargs["supported_model_families"])
    if "parameter_surface" in kwargs:
        kwargs["parameter_surface"] = json.dumps(kwargs["parameter_surface"])

    r = await runner_service.create_runner(session, **kwargs)
    result = _runner_to_dict(r)
    await session.commit()
    return result


@router.get("/{runner_id}", response_model=RunnerResponse)
async def get_runner(
    runner_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    r = await runner_service.get_runner(session, runner_id)
    if r is None:
        raise HTTPException(404, "Runner not found")
    return _runner_to_dict(r)


@router.put("/{runner_id}", response_model=RunnerResponse)
async def update_runner(
    runner_id: int,
    body: RunnerUpdate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    kwargs = body.model_dump(exclude_none=True)
    if "supported_machine_classes" in kwargs:
        kwargs["supported_machine_classes"] = json.dumps(kwargs["supported_machine_classes"])
    if "supported_model_families" in kwargs:
        kwargs["supported_model_families"] = json.dumps(kwargs["supported_model_families"])
    if "parameter_surface" in kwargs:
        kwargs["parameter_surface"] = json.dumps(kwargs["parameter_surface"])

    r = await runner_service.update_runner(session, runner_id, **kwargs)
    if r is None:
        raise HTTPException(404, "Runner not found")
    result = _runner_to_dict(r)
    await session.commit()
    return result


def _runner_to_dict(r) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "runner_class": r.runner_class,
        "display_name": r.display_name,
        "version": r.version,
        "supported_machine_classes": (
            json.loads(r.supported_machine_classes) if r.supported_machine_classes else None
        ),
        "supported_model_families": (
            json.loads(r.supported_model_families) if r.supported_model_families else None
        ),
        "parameter_surface": (json.loads(r.parameter_surface) if r.parameter_surface else None),
        "default_endpoint_url": r.default_endpoint_url,
        "notes": r.notes,
        "is_archived": r.is_archived,
        "created_at": r.created_at,
    }
