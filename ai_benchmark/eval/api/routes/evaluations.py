"""Evaluation CRUD routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from ...services import eval_service
from ..app import get_session
from ..schemas.evaluation import (
    EvaluationCreate,
    EvaluationResponse,
    EvaluationUpdate,
    EvaluationVersionCreate,
    EvaluationVersionResponse,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[EvaluationResponse])
async def list_evaluations(
    name: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
):
    evals = await eval_service.list_evaluations(
        session, name=name, tag=tag, include_archived=include_archived
    )
    results = []
    for e in evals:
        data = _eval_to_dict(e)
        results.append(data)
    return results


@router.post("", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(
    body: EvaluationCreate,
    session: AsyncSession = Depends(get_session),
):
    e = await eval_service.create_evaluation(
        session,
        name=body.name,
        description=body.description,
        owner=body.owner,
        tags=body.tags,
        suite_name=body.suite_name,
        execution_mode=body.execution_mode,
    )
    result = _eval_to_dict(e)
    await session.commit()
    return result


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: int,
    session: AsyncSession = Depends(get_session),
):
    e = await eval_service.get_evaluation(session, evaluation_id)
    if e is None:
        raise HTTPException(404, "Evaluation not found")
    return _eval_to_dict(e)


@router.put("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: int,
    body: EvaluationUpdate,
    session: AsyncSession = Depends(get_session),
):
    kwargs = body.model_dump(exclude_none=True)
    e = await eval_service.update_evaluation(session, evaluation_id, **kwargs)
    if e is None:
        raise HTTPException(404, "Evaluation not found")
    result = _eval_to_dict(e)
    await session.commit()
    return result


@router.post(
    "/{evaluation_id}/versions",
    response_model=EvaluationVersionResponse,
    status_code=201,
)
async def create_version(
    evaluation_id: int,
    body: EvaluationVersionCreate,
    session: AsyncSession = Depends(get_session),
):
    ev = await eval_service.create_version(
        session,
        evaluation_id=evaluation_id,
        dataset_version_id=body.dataset_version_id,
        scorer_config=body.scorer_config,
        prompt_template=body.prompt_template,
        preprocessing=body.preprocessing,
        pass_criteria=body.pass_criteria,
        notes=body.notes,
    )
    result = _version_to_dict(ev)
    await session.commit()
    return result


@router.get(
    "/{evaluation_id}/versions/{version_number}",
    response_model=EvaluationVersionResponse,
)
async def get_version(
    evaluation_id: int,
    version_number: int,
    session: AsyncSession = Depends(get_session),
):
    ev = await eval_service.get_version(session, evaluation_id, version_number)
    if ev is None:
        raise HTTPException(404, "Evaluation version not found")
    return _version_to_dict(ev)


def _eval_to_dict(e) -> dict:
    d = {
        "id": e.id,
        "name": e.name,
        "description": e.description,
        "owner": e.owner,
        "suite_name": e.suite_name,
        "execution_mode": e.execution_mode,
        "is_archived": e.is_archived,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }
    d["tags"] = json.loads(e.tags) if e.tags else None
    return d


def _version_to_dict(ev) -> dict:
    return {
        "id": ev.id,
        "evaluation_id": ev.evaluation_id,
        "version_number": ev.version_number,
        "dataset_version_id": ev.dataset_version_id,
        "scorer_config": json.loads(ev.scorer_config) if ev.scorer_config else None,
        "prompt_template": ev.prompt_template,
        "preprocessing": json.loads(ev.preprocessing) if ev.preprocessing else None,
        "pass_criteria": json.loads(ev.pass_criteria) if ev.pass_criteria else None,
        "notes": ev.notes,
        "created_at": ev.created_at,
    }
