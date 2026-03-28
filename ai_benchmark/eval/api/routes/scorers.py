"""Scorer CRUD routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import get_session
from ..schemas.scorer import (
    ScorerCreate,
    ScorerResponse,
    ScorerVersionCreate,
    ScorerVersionResponse,
)
from ...services import scorer_service

router = APIRouter()


@router.get("", response_model=list[ScorerResponse])
async def list_scorers(
    scorer_type: str | None = None,
    name: str | None = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
):
    scorers = await scorer_service.list_scorers(
        session, scorer_type=scorer_type, name=name, include_archived=include_archived
    )
    return [_scorer_to_dict(s) for s in scorers]


@router.post("", response_model=ScorerResponse, status_code=201)
async def create_scorer(
    body: ScorerCreate,
    session: AsyncSession = Depends(get_session),
):
    s = await scorer_service.create_scorer(
        session, name=body.name, scorer_type=body.scorer_type,
        description=body.description, tags=body.tags,
    )
    result = _scorer_to_dict(s)

    await session.commit()

    return result


@router.get("/{scorer_id}", response_model=ScorerResponse)
async def get_scorer(
    scorer_id: int,
    session: AsyncSession = Depends(get_session),
):
    s = await scorer_service.get_scorer(session, scorer_id)
    if s is None:
        raise HTTPException(404, "Scorer not found")
    return _scorer_to_dict(s)


@router.post(
    "/{scorer_id}/versions",
    response_model=ScorerVersionResponse,
    status_code=201,
)
async def create_version(
    scorer_id: int,
    body: ScorerVersionCreate,
    session: AsyncSession = Depends(get_session),
):
    sv = await scorer_service.create_version(
        session, scorer_id=scorer_id, config=body.config,
        implementation_ref=body.implementation_ref, notes=body.notes,
    )
    result = _version_to_dict(sv)

    await session.commit()

    return result


def _scorer_to_dict(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "scorer_type": s.scorer_type,
        "description": s.description,
        "tags": json.loads(s.tags) if s.tags else None,
        "is_archived": s.is_archived,
        "created_at": s.created_at,
    }


def _version_to_dict(sv) -> dict:
    return {
        "id": sv.id,
        "scorer_id": sv.scorer_id,
        "version_number": sv.version_number,
        "config": json.loads(sv.config) if sv.config else None,
        "implementation_ref": sv.implementation_ref,
        "notes": sv.notes,
        "created_at": sv.created_at,
    }
