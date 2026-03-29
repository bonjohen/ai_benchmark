"""Dataset CRUD routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ...services import dataset_service
from ..app import get_session
from ..schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetVersionCreate,
    DatasetVersionResponse,
    ItemFilterRequest,
    TestCaseResponse,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    name: str | None = None,
    source: str | None = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
):
    datasets = await dataset_service.list_datasets(
        session, name=name, source=source, include_archived=include_archived
    )
    return [_ds_to_dict(d) for d in datasets]


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    body: DatasetCreate,
    session: AsyncSession = Depends(get_session),
):
    d = await dataset_service.create_dataset(
        session,
        name=body.name,
        description=body.description,
        source=body.source,
        tags=body.tags,
    )
    result = _ds_to_dict(d)

    await session.commit()

    return result


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
):
    d = await dataset_service.get_dataset(session, dataset_id)
    if d is None:
        raise HTTPException(404, "Dataset not found")
    return _ds_to_dict(d)


@router.post(
    "/{dataset_id}/versions",
    response_model=DatasetVersionResponse,
    status_code=201,
)
async def create_version(
    dataset_id: int,
    body: DatasetVersionCreate,
    session: AsyncSession = Depends(get_session),
):
    items = [item.model_dump() for item in body.items]
    dv = await dataset_service.create_version(
        session,
        dataset_id=dataset_id,
        items=items,
        notes=body.notes,
    )
    result = _version_to_dict(dv)

    await session.commit()

    return result


@router.get(
    "/{dataset_id}/versions/{version_number}",
    response_model=DatasetVersionResponse,
)
async def get_version(
    dataset_id: int,
    version_number: int,
    session: AsyncSession = Depends(get_session),
):
    dv = await dataset_service.get_version(session, dataset_id, version_number)
    if dv is None:
        raise HTTPException(404, "Dataset version not found")
    return _version_to_dict(dv)


@router.get(
    "/{dataset_id}/versions/{version_number}/items",
    response_model=list[TestCaseResponse],
)
async def list_items(
    dataset_id: int,
    version_number: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    tag: str | None = None,
    difficulty: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    dv = await dataset_service.get_version(session, dataset_id, version_number)
    if dv is None:
        raise HTTPException(404, "Dataset version not found")
    items = await dataset_service.list_items(
        session,
        dv.id,
        limit=limit,
        offset=offset,
        tag=tag,
        difficulty=difficulty,
    )
    return [_item_to_dict(i) for i in items]


@router.post(
    "/{dataset_id}/versions/{version_number}/filter",
    response_model=list[int],
)
async def filter_items(
    dataset_id: int,
    version_number: int,
    body: ItemFilterRequest,
    session: AsyncSession = Depends(get_session),
):
    dv = await dataset_service.get_version(session, dataset_id, version_number)
    if dv is None:
        raise HTTPException(404, "Dataset version not found")
    return await dataset_service.filter_items(
        session,
        dv.id,
        tags=body.tags,
        task_families=body.task_families,
        min_tokens=body.min_tokens,
        max_tokens=body.max_tokens,
    )


def _ds_to_dict(d) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "source": d.source,
        "tags": json.loads(d.tags) if d.tags else None,
        "is_archived": d.is_archived,
        "created_at": d.created_at,
    }


def _version_to_dict(dv) -> dict:
    return {
        "id": dv.id,
        "dataset_id": dv.dataset_id,
        "version_number": dv.version_number,
        "item_count": dv.item_count,
        "checksum": dv.checksum,
        "notes": dv.notes,
        "created_at": dv.created_at,
    }


def _item_to_dict(tc) -> dict:
    return {
        "id": tc.id,
        "dataset_version_id": tc.dataset_version_id,
        "item_index": tc.item_index,
        "input_text": tc.input_text,
        "expected_output": tc.expected_output,
        "context": tc.context,
        "metadata": json.loads(tc.metadata_json) if tc.metadata_json else None,
        "created_at": tc.created_at,
    }
