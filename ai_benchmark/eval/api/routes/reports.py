"""Report generation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ...services import report_service
from ..app import get_session
from ..schemas.comparison import PresetCreate, PresetResponse, ReportRequest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/summary")
async def generate_summary(
    body: ReportRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await report_service.generate_summary(
        session,
        group_by=body.group_by or "evaluation",
    )

    if body.format == "csv":
        rows = result.get("rows", [])
        return PlainTextResponse(
            report_service.export_csv(rows) if rows else "No data",
            media_type="text/csv",
        )
    elif body.format == "html":
        return PlainTextResponse(
            report_service.export_html(result, title="Evaluation Summary"),
            media_type="text/html",
        )
    return result


@router.get("/presets", response_model=list[PresetResponse])
async def list_presets():
    presets = report_service.list_presets()
    return [{"name": p["name"], "config": p.get("config", {})} for p in presets]


@router.post("/presets", response_model=PresetResponse, status_code=201)
async def save_preset(body: PresetCreate):
    import hashlib

    preset_id = hashlib.md5(body.name.encode()).hexdigest()[:8]
    result = report_service.save_preset(preset_id, body.name, body.config)
    return {"name": result["name"], "config": result.get("config", {})}


@router.post("/presets/{preset_id}/run")
async def run_preset(
    preset_id: str,
    session: AsyncSession = Depends(get_session),
):
    return await report_service.run_preset(session, preset_id)
