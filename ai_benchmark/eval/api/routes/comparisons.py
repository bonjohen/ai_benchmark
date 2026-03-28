"""Comparison and config diff routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import get_session
from ..schemas.comparison import (
    CompareRequest,
    CompareResponse,
    ConfigDiffRequest,
    ConfigDiffResponse,
)
from ...services import comparison_service

router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
async def compare_runs(
    body: CompareRequest,
    session: AsyncSession = Depends(get_session),
):
    if len(body.run_ids) < 2:
        raise HTTPException(400, "At least 2 run IDs required")
    result = await comparison_service.compare_runs(session, body.run_ids)
    return result


@router.post("/config-diff", response_model=ConfigDiffResponse)
async def config_diff(
    body: ConfigDiffRequest,
    session: AsyncSession = Depends(get_session),
):
    if len(body.target_ids) < 2:
        raise HTTPException(400, "At least 2 target IDs required")
    result = await comparison_service.diff_target_configs(session, body.target_ids)
    return {"diffs": result}
