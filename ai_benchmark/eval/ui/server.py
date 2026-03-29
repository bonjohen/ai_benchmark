"""Mount Jinja2 templates and static files on the FastAPI app."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.app import get_session

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


# ── Dashboard ────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    """Main dashboard — active runs, recent completions, alerts."""
    from ..services import machine_service, run_service

    active_runs = []
    for status in ("queued", "running", "scoring"):
        runs = await run_service.list_runs(session, status=status)
        active_runs.extend(runs)

    recent_runs = await run_service.list_runs(session, limit=10)
    machines = await machine_service.list_profiles(session)

    # Convert ORM objects to dicts before template rendering
    active_data = [_run_to_dict(r) for r in active_runs]
    recent_data = [_run_to_dict(r) for r in recent_runs]
    machine_data = [_machine_to_dict(m) for m in machines]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_runs": active_data,
            "recent_runs": recent_data,
            "machines": machine_data,
        },
    )


# ── Evaluations ──────────────────────────────────────────────────────────


@router.get("/evaluations", response_class=HTMLResponse)
async def evaluation_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import eval_service

    items = await eval_service.list_evaluations(session)
    data = [_eval_to_dict(e) for e in items]
    return templates.TemplateResponse(
        "evaluations/list.html",
        {
            "request": request,
            "evaluations": data,
        },
    )


@router.get("/evaluations/create", response_class=HTMLResponse)
async def evaluation_create_form(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import dataset_service, scorer_service

    datasets = await dataset_service.list_datasets(session)
    scorers = await scorer_service.list_scorers(session)
    return templates.TemplateResponse(
        "evaluations/create.html",
        {
            "request": request,
            "datasets": [{"id": d.id, "name": d.name} for d in datasets],
            "scorers": [
                {"id": s.id, "name": s.name, "scorer_type": s.scorer_type} for s in scorers
            ],
        },
    )


@router.get("/evaluations/{eval_id}", response_class=HTMLResponse)
async def evaluation_detail(
    request: Request, eval_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.evaluation import EvaluationVersion
    from ..services import eval_service, run_service

    ev = await eval_service.get_evaluation(session, eval_id)
    if ev is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    stmt = (
        select(EvaluationVersion)
        .where(EvaluationVersion.evaluation_id == eval_id)
        .order_by(EvaluationVersion.version_number.desc())
    )
    result = await session.execute(stmt)
    versions = [_version_to_dict(v) for v in result.scalars().all()]

    runs = await run_service.list_runs(session, limit=20)
    recent_runs = [
        _run_to_dict(r) for r in runs if r.evaluation_version_id in {v["id"] for v in versions}
    ]

    return templates.TemplateResponse(
        "evaluations/detail.html",
        {
            "request": request,
            "evaluation": _eval_to_dict(ev),
            "versions": versions,
            "recent_runs": recent_runs,
        },
    )


# ── Datasets ─────────────────────────────────────────────────────────────


@router.get("/datasets", response_class=HTMLResponse)
async def dataset_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import dataset_service

    items = await dataset_service.list_datasets(session)
    data = [_dataset_to_dict(d) for d in items]
    return templates.TemplateResponse(
        "datasets/list.html",
        {
            "request": request,
            "datasets": data,
        },
    )


@router.get("/datasets/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail(
    request: Request, dataset_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.dataset import DatasetVersion
    from ..services import dataset_service

    ds = await dataset_service.get_dataset(session, dataset_id)
    if ds is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
    )
    result = await session.execute(stmt)
    versions = []
    for v in result.scalars().all():
        versions.append(
            {
                "id": v.id,
                "version_number": v.version_number,
                "item_count": v.item_count,
                "checksum": v.checksum,
                "created_at": str(v.created_at) if v.created_at else None,
            }
        )

    return templates.TemplateResponse(
        "datasets/detail.html",
        {
            "request": request,
            "dataset": _dataset_to_dict(ds),
            "versions": versions,
        },
    )


# ── Scorers ──────────────────────────────────────────────────────────────


@router.get("/scorers", response_class=HTMLResponse)
async def scorer_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import scorer_service

    items = await scorer_service.list_scorers(session)
    data = [
        {
            "id": s.id,
            "name": s.name,
            "scorer_type": s.scorer_type,
            "created_at": str(s.created_at) if s.created_at else None,
        }
        for s in items
    ]
    return templates.TemplateResponse(
        "scorers/list.html",
        {
            "request": request,
            "scorers": data,
        },
    )


# ── Targets ──────────────────────────────────────────────────────────────


@router.get("/targets", response_class=HTMLResponse)
async def target_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import target_service

    items = await target_service.list_targets(session)
    data = [_target_to_dict(t) for t in items]
    return templates.TemplateResponse(
        "targets/list.html",
        {
            "request": request,
            "targets": data,
        },
    )


@router.get("/targets/{target_id}", response_class=HTMLResponse)
async def target_detail(
    request: Request, target_id: int, session: AsyncSession = Depends(get_session)
):
    from ..services import run_service, target_service

    t = await target_service.get_target(session, target_id)
    if t is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    runs = await run_service.list_runs(session, limit=50)
    target_runs = [_run_to_dict(r) for r in runs if r.target_config_id == target_id]

    return templates.TemplateResponse(
        "targets/detail.html",
        {
            "request": request,
            "target": _target_to_dict(t),
            "runs": target_runs,
        },
    )


# ── Machines ─────────────────────────────────────────────────────────────


@router.get("/machines", response_class=HTMLResponse)
async def machine_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import machine_service

    items = await machine_service.list_profiles(session)
    data = [_machine_to_dict(m) for m in items]
    return templates.TemplateResponse(
        "machines/list.html",
        {
            "request": request,
            "machines": data,
        },
    )


# ── Runs ─────────────────────────────────────────────────────────────────


@router.get("/runs", response_class=HTMLResponse)
async def run_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import run_service

    runs = await run_service.list_runs(session, limit=50)
    data = [_run_to_dict(r) for r in runs]
    return templates.TemplateResponse(
        "runs/list.html",
        {
            "request": request,
            "runs": data,
        },
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: int, session: AsyncSession = Depends(get_session)):
    from ..services import run_service

    run = await run_service.get_run(session, run_id)
    if run is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    items = await run_service.get_item_results(session, run_id, limit=100)
    metrics = await run_service.get_metrics(session, run_id)
    artifacts = await run_service.list_artifacts(session, run_id)

    item_data = []
    for i in items:
        item_data.append(
            {
                "id": i.id,
                "item_index": i.item_index,
                "input_text": (i.input_text or "")[:200],
                "raw_output": (i.raw_output or "")[:200],
                "overall_pass": i.overall_pass,
                "latency_ms": i.latency_ms,
                "error_message": i.error_message,
            }
        )

    metric_data = [{"metric_name": m.metric_name, "metric_value": m.metric_value} for m in metrics]
    artifact_data = [
        {
            "id": a.id,
            "filename": a.filename,
            "artifact_type": a.artifact_type,
            "size_bytes": a.size_bytes,
        }
        for a in artifacts
    ]

    return templates.TemplateResponse(
        "runs/detail.html",
        {
            "request": request,
            "run": _run_to_dict(run),
            "items": item_data,
            "metrics": metric_data,
            "artifacts": artifact_data,
        },
    )


@router.get("/runs/{run_id}/live", response_class=HTMLResponse)
async def run_live(request: Request, run_id: int, session: AsyncSession = Depends(get_session)):
    from ..services import run_service

    run = await run_service.get_run(session, run_id)
    if run is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    items = await run_service.get_item_results(session, run_id, limit=100)
    item_data = [
        {
            "id": i.id,
            "item_index": i.item_index,
            "overall_pass": i.overall_pass,
            "latency_ms": i.latency_ms,
            "error_message": i.error_message,
        }
        for i in items
    ]

    return templates.TemplateResponse(
        "runs/live.html",
        {
            "request": request,
            "run": _run_to_dict(run),
            "items": item_data,
        },
    )


# ── Comparisons ──────────────────────────────────────────────────────────


@router.get("/comparisons", response_class=HTMLResponse)
async def comparison_page(
    request: Request, runs: str | None = None, session: AsyncSession = Depends(get_session)
):
    comparison = None
    run_details = []

    if runs:
        from ..services import comparison_service, run_service

        run_ids = [int(r.strip()) for r in runs.split(",") if r.strip()]
        if len(run_ids) >= 2:
            comparison = await comparison_service.compare_runs(session, run_ids)
            comparison["run_ids"] = run_ids

            # Also fetch run details and items for each run
            for rid in run_ids:
                r = await run_service.get_run(session, rid)
                if r:
                    items = await run_service.get_item_results(session, rid, limit=1000)
                    run_details.append(
                        {
                            "run": _run_to_dict(r),
                            "items": [
                                {
                                    "item_index": i.item_index,
                                    "raw_output": (i.raw_output or "")[:300],
                                    "overall_pass": i.overall_pass,
                                    "latency_ms": i.latency_ms,
                                }
                                for i in items
                            ],
                        }
                    )

            # Config diff
            target_ids = []
            for rid in run_ids:
                r = await run_service.get_run(session, rid)
                if r:
                    target_ids.append(r.target_config_id)
            if len(set(target_ids)) > 1:
                config_diff = await comparison_service.diff_target_configs(session, target_ids)
                comparison["config_diff"] = config_diff

    return templates.TemplateResponse(
        "comparisons/compare.html",
        {
            "request": request,
            "comparison": comparison,
            "run_details": run_details,
        },
    )


# ── Reports ──────────────────────────────────────────────────────────────


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import report_service, run_service

    presets = await report_service.list_presets(session)
    preset_data = [
        {"id": p.id, "name": p.name, "description": getattr(p, "description", "")} for p in presets
    ]

    # Gather chart data from recent runs
    runs = await run_service.list_runs(session, limit=50)
    chart_data = []
    for r in runs:
        metrics = await run_service.get_metrics(session, r.id)
        metric_dict = {m.metric_name: m.metric_value for m in metrics}
        chart_data.append(
            {
                "run_id": r.id,
                "status": r.status,
                "target_config_id": r.target_config_id,
                "pass_rate": metric_dict.get("pass_rate"),
                "avg_latency_ms": metric_dict.get("avg_latency_ms"),
                "total_cost_usd": metric_dict.get("total_cost_usd"),
                "created_at": str(r.created_at) if r.created_at else None,
            }
        )

    return templates.TemplateResponse(
        "reports/dashboard.html",
        {
            "request": request,
            "presets": preset_data,
            "chart_data": chart_data,
        },
    )


@router.get("/reports/export", response_class=HTMLResponse)
async def report_export(
    request: Request, format: str = "json", session: AsyncSession = Depends(get_session)
):
    """Export recent run data as JSON/CSV/HTML download."""
    from ..services import report_service, run_service

    runs = await run_service.list_runs(session, limit=100)
    rows = []
    for r in runs:
        metrics = await run_service.get_metrics(session, r.id)
        row = _run_to_dict(r)
        for m in metrics:
            row[m.metric_name] = m.metric_value
        rows.append(row)

    if format == "csv":
        content = report_service.export_csv(rows)
        media_type = "text/csv"
        filename = "eval_report.csv"
    elif format == "html":
        content = report_service.export_html({"runs": rows}, title="Eval Report")
        media_type = "text/html"
        filename = "eval_report.html"
    else:
        content = report_service.export_json(rows)
        media_type = "application/json"
        filename = "eval_report.json"

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _run_to_dict(r) -> dict:
    return {
        "id": r.id,
        "status": r.status,
        "total_items": r.total_items,
        "completed_items": r.completed_items,
        "failed_items": r.failed_items,
        "trigger_type": r.trigger_type,
        "priority": r.priority,
        "started_at": str(r.started_at) if r.started_at else None,
        "completed_at": str(r.completed_at) if r.completed_at else None,
        "error_message": r.error_message,
        "evaluation_version_id": r.evaluation_version_id,
        "target_config_id": r.target_config_id,
        "created_at": str(r.created_at) if r.created_at else None,
    }


def _eval_to_dict(e) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "description": e.description,
        "owner": e.owner,
        "execution_mode": e.execution_mode,
        "is_archived": e.is_archived,
        "created_at": str(e.created_at) if e.created_at else None,
    }


def _version_to_dict(v) -> dict:
    return {
        "id": v.id,
        "version_number": v.version_number,
        "evaluation_id": v.evaluation_id,
        "dataset_version_id": v.dataset_version_id,
        "scorer_config": v.scorer_config,
        "created_at": str(v.created_at) if v.created_at else None,
    }


def _dataset_to_dict(d) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "source": d.source,
        "is_archived": d.is_archived,
        "created_at": str(d.created_at) if d.created_at else None,
    }


def _target_to_dict(t) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "model_name": t.model_name,
        "model_family": t.model_family,
        "provider": t.provider,
        "endpoint_url": t.endpoint_url,
        "runtime_backend": t.runtime_backend,
        "is_archived": t.is_archived,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _machine_to_dict(m) -> dict:
    return {
        "id": m.id,
        "hostname": m.hostname,
        "display_name": m.display_name,
        "hardware_class": m.hardware_class,
        "cpu_description": m.cpu_description,
        "gpu_description": m.gpu_description,
        "ram_gb": m.ram_gb,
        "created_at": str(m.created_at) if m.created_at else None,
    }


def mount_ui(app):
    """Mount the UI routes and static files on the given FastAPI app."""
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router, prefix="/eval", tags=["ui"])
