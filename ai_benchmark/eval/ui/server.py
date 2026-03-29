"""Mount Jinja2 templates and static files on the FastAPI app."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..api.app import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


# ── Dashboard ────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    """Main dashboard — current activity vs recent history."""
    from ..services import machine_service, run_service, runner_service

    # Current activity: queued, running, scoring
    active_runs = []
    for status in ("queued", "running", "scoring"):
        runs = await run_service.list_runs(session, status=status)
        active_runs.extend(runs)

    # Historical: completed/failed runs (exclude active statuses)
    all_recent = await run_service.list_runs(session, limit=15)
    completed_runs = [
        r
        for r in all_recent
        if r.status in ("completed", "failed", "canceled", "partially_completed")
    ]

    machines = await machine_service.list_profiles(session)
    runners = await runner_service.list_runners(session)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_runs": [_run_to_dict(r) for r in active_runs],
            "completed_runs": [_run_to_dict(r) for r in completed_runs],
            "machines": [_machine_to_dict(m) for m in machines],
            "runners": runners,
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


@router.post("/evaluations/{eval_id}/archive", response_class=HTMLResponse)
async def evaluation_archive(
    request: Request, eval_id: int, session: AsyncSession = Depends(get_session)
):
    from ..services import eval_service

    await eval_service.update_evaluation(session, eval_id, is_archived=True)
    await session.commit()
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/eval/evaluations/{eval_id}", status_code=303)


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


@router.get(
    "/datasets/{dataset_id}/versions/{version_id}/preview",
    response_class=HTMLResponse,
)
async def dataset_version_preview(
    request: Request,
    dataset_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_session),
):
    from ..services import dataset_service

    ds = await dataset_service.get_dataset(session, dataset_id)
    if ds is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    from sqlalchemy import select

    from ..models.dataset import DatasetVersion

    stmt = select(DatasetVersion).where(DatasetVersion.id == version_id)
    result = await session.execute(stmt)
    dv = result.scalar_one_or_none()
    if dv is None:
        return HTMLResponse("<h1>Version Not Found</h1>", status_code=404)

    items = await dataset_service.list_items(session, version_id, limit=50)
    item_data = []
    for tc in items:
        meta = {}
        if tc.metadata_json:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                meta = json.loads(tc.metadata_json)
        item_data.append(
            {
                "item_index": tc.item_index,
                "input_text": (tc.input_text or "")[:300],
                "expected_output": (tc.expected_output or "")[:300],
                "tags": meta.get("tags", ""),
                "difficulty": meta.get("difficulty", ""),
            }
        )

    return templates.TemplateResponse(
        "datasets/preview.html",
        {
            "request": request,
            "dataset": _dataset_to_dict(ds),
            "version": {
                "id": dv.id,
                "version_number": dv.version_number,
                "item_count": dv.item_count,
                "checksum": dv.checksum,
            },
            "items": item_data,
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


@router.get("/scorers/{scorer_id}", response_class=HTMLResponse)
async def scorer_detail(
    request: Request, scorer_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.scorer import ScorerVersion
    from ..services import scorer_service

    scorer = await scorer_service.get_scorer(session, scorer_id)
    if scorer is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    stmt = (
        select(ScorerVersion)
        .where(ScorerVersion.scorer_id == scorer_id)
        .order_by(ScorerVersion.version_number.desc())
    )
    result = await session.execute(stmt)
    versions = [
        {
            "id": v.id,
            "version_number": v.version_number,
            "config": v.config,
            "implementation_ref": v.implementation_ref,
            "notes": v.notes,
            "created_at": str(v.created_at) if v.created_at else None,
        }
        for v in result.scalars().all()
    ]

    return templates.TemplateResponse(
        "scorers/detail.html",
        {
            "request": request,
            "scorer": {
                "id": scorer.id,
                "name": scorer.name,
                "scorer_type": scorer.scorer_type,
                "description": scorer.description,
                "created_at": str(scorer.created_at) if scorer.created_at else None,
            },
            "versions": versions,
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


@router.get("/targets/{target_id}/clone", response_class=HTMLResponse)
async def target_clone_form(
    request: Request, target_id: int, session: AsyncSession = Depends(get_session)
):
    from ..services import target_service

    t = await target_service.get_target(session, target_id)
    if t is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    return templates.TemplateResponse(
        "targets/clone.html",
        {"request": request, "target": _target_to_dict(t)},
    )


@router.post("/targets/{target_id}/clone", response_class=HTMLResponse)
async def target_clone_submit(
    request: Request, target_id: int, session: AsyncSession = Depends(get_session)
):
    from ..services import target_service

    form = await request.form()
    new_name = form.get("new_name", "").strip()
    if not new_name:
        new_name = f"Clone of target {target_id}"

    cloned = await target_service.clone_target(session, target_id, new_name=new_name)
    await session.commit()
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/eval/targets/{cloned.id}", status_code=303)


# ── Runners ──────────────────────────────────────────────────────────────


@router.get("/runners", response_class=HTMLResponse)
async def runner_list(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import runner_service

    runner_class = request.query_params.get("runner_class") or None
    items = await runner_service.list_runners(session, runner_class=runner_class)
    data = [_runner_to_dict(r) for r in items]

    # Distinct runner classes for filter dropdown
    all_runners = await runner_service.list_runners(session)
    runner_classes = sorted({r.runner_class for r in all_runners})

    return templates.TemplateResponse(
        "runners/list.html",
        {
            "request": request,
            "runners": data,
            "runner_classes": runner_classes,
        },
    )


@router.get("/runners/{runner_id}", response_class=HTMLResponse)
async def runner_detail(
    request: Request, runner_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.target import TargetConfiguration
    from ..services import run_service, runner_service

    runner = await runner_service.get_runner(session, runner_id)
    if runner is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    runner_data = _runner_to_dict(runner)

    # Find target configs using this runner
    stmt = select(TargetConfiguration).where(TargetConfiguration.runner_profile_id == runner_id)
    result = await session.execute(stmt)
    targets = [_target_to_dict(t) for t in result.scalars().all()]

    # Find runs via those targets
    target_ids = {t["id"] for t in targets}
    runs = []
    if target_ids:
        all_runs = await run_service.list_runs(session, limit=50)
        runs = [_run_to_dict(r) for r in all_runs if r.target_config_id in target_ids]

    return templates.TemplateResponse(
        "runners/detail.html",
        {
            "request": request,
            "runner": runner_data,
            "targets": targets,
            "runs": runs,
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


@router.get("/machines/{machine_id}", response_class=HTMLResponse)
async def machine_detail(
    request: Request, machine_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.machine import MachineSnapshot
    from ..models.target import TargetConfiguration
    from ..services import machine_service

    machine = await machine_service.get_profile(session, machine_id)
    if machine is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    runtime_avail = []
    if machine.runtime_availability:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            runtime_avail = json.loads(machine.runtime_availability)

    accel_details = None
    if machine.accelerator_details:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            accel_details = json.dumps(json.loads(machine.accelerator_details), indent=2)
        if accel_details is None:
            accel_details = machine.accelerator_details

    machine_data = {
        **_machine_to_dict(machine),
        "storage_summary": machine.storage_summary,
        "os_description": machine.os_description,
        "accelerator_details": accel_details,
        "capacity_notes": machine.capacity_notes,
        "runtime_availability": runtime_avail,
    }

    # Snapshots
    snap_stmt = (
        select(MachineSnapshot)
        .where(MachineSnapshot.machine_profile_id == machine_id)
        .order_by(MachineSnapshot.captured_at.desc())
        .limit(20)
    )
    snap_result = await session.execute(snap_stmt)
    snapshots = [
        {
            "id": s.id,
            "runtime_version": None,
            "model_server_version": None,
            "created_at": str(s.captured_at) if s.captured_at else None,
        }
        for s in snap_result.scalars().all()
    ]

    # Target configs on this machine
    tgt_stmt = select(TargetConfiguration).where(
        TargetConfiguration.machine_profile_id == machine_id
    )
    tgt_result = await session.execute(tgt_stmt)
    targets = [_target_to_dict(t) for t in tgt_result.scalars().all()]

    return templates.TemplateResponse(
        "machines/detail.html",
        {
            "request": request,
            "machine": machine_data,
            "snapshots": snapshots,
            "targets": targets,
        },
    )


# ── Runs ─────────────────────────────────────────────────────────────────


@router.get("/runs", response_class=HTMLResponse)
async def run_list(request: Request, session: AsyncSession = Depends(get_session)):
    from datetime import datetime

    from ..services import eval_service, machine_service, run_service

    # Parse filter params
    status = request.query_params.get("status") or None
    evaluation_id = request.query_params.get("evaluation_id") or None
    model_name = request.query_params.get("model_name") or None
    hardware_class = request.query_params.get("hardware_class") or None
    date_from_str = request.query_params.get("date_from") or None
    date_to_str = request.query_params.get("date_to") or None

    date_from = None
    date_to = None
    if date_from_str:
        with contextlib.suppress(ValueError):
            date_from = datetime.fromisoformat(date_from_str)
    if date_to_str:
        with contextlib.suppress(ValueError):
            date_to = datetime.fromisoformat(date_to_str)

    runs = await run_service.list_runs(
        session,
        status=status,
        evaluation_id=int(evaluation_id) if evaluation_id else None,
        model_name=model_name,
        hardware_class=hardware_class,
        date_from=date_from,
        date_to=date_to,
        limit=100,
    )
    data = [_run_to_dict(r) for r in runs]

    # Load entity lists for filter dropdowns
    evaluations = await eval_service.list_evaluations(session)
    eval_data = [{"id": e.id, "name": e.name} for e in evaluations]

    machines = await machine_service.list_profiles(session)
    hw_classes = sorted({m.hardware_class for m in machines if m.hardware_class})

    return templates.TemplateResponse(
        "runs/list.html",
        {
            "request": request,
            "runs": data,
            "evaluations": eval_data,
            "hardware_classes": hw_classes,
            "filter_status": status,
            "filter_evaluation_id": int(evaluation_id) if evaluation_id else None,
            "filter_model_name": model_name,
            "filter_hardware_class": hardware_class,
            "filter_date_from": date_from_str,
            "filter_date_to": date_to_str,
        },
    )


@router.get("/runs/launch", response_class=HTMLResponse)
async def run_launch_form(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import eval_service, machine_service, target_service

    evaluations = await eval_service.list_evaluations(session)
    eval_data = [_eval_to_dict(e) for e in evaluations]

    targets = await target_service.list_targets(session)
    machines = await machine_service.list_profiles(session)
    machine_map = {m.id: m for m in machines}

    target_data = []
    for t in targets:
        td = _target_to_dict(t)
        mp = machine_map.get(t.machine_profile_id) if t.machine_profile_id else None
        td["machine_name"] = mp.display_name or mp.hostname if mp else None
        target_data.append(td)

    # Check for validation warnings
    warnings_list = []
    try:
        from ..services.compatibility import is_compatible

        for t in targets:
            if t.machine_profile_id and t.runner_profile_id:
                mp = machine_map.get(t.machine_profile_id)
                if mp and not is_compatible(t.runner_profile_id, mp.hardware_class):
                    warnings_list.append(
                        f"Target '{t.name}' may have incompatible runner/machine combination"
                    )
    except Exception:  # noqa: BLE001
        pass  # Compatibility check is best-effort

    return templates.TemplateResponse(
        "runs/launch.html",
        {
            "request": request,
            "evaluations": eval_data,
            "targets": target_data,
            "validation_warnings": warnings_list,
        },
    )


@router.post("/runs/launch", response_class=HTMLResponse)
async def run_launch_submit(request: Request, session: AsyncSession = Depends(get_session)):
    """Create a run from the launch form."""
    from ..services import run_service

    form = await request.form()
    target_ids = form.getlist("target_ids")
    if not target_ids:
        from starlette.responses import RedirectResponse

        return RedirectResponse("/eval/runs/launch", status_code=303)

    # For simplicity, create runs directly (the orchestrator would be used
    # in real execution — this creates the DB records for the UI flow)
    first_run_id = None
    for tid in target_ids:
        run = await run_service.create_run(
            session,
            evaluation_version_id=1,  # Would come from selected evaluation
            target_config_id=int(tid),
            trigger_type="ui",
            priority=int(form.get("priority", 0)),
        )
        if first_run_id is None:
            first_run_id = run.id

    await session.commit()
    from starlette.responses import RedirectResponse

    if first_run_id:
        return RedirectResponse(f"/eval/runs/{first_run_id}", status_code=303)
    return RedirectResponse("/eval/runs", status_code=303)


@router.post("/runs/{run_id}/cancel", response_class=HTMLResponse)
async def run_cancel(request: Request, run_id: int, session: AsyncSession = Depends(get_session)):
    from ..services import run_service

    await run_service.update_status(session, run_id, "canceled")
    await session.commit()
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/eval/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/resume", response_class=HTMLResponse)
async def run_resume(request: Request, run_id: int, session: AsyncSession = Depends(get_session)):
    from ..services import run_service

    await run_service.update_status(session, run_id, "queued")
    await session.commit()
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/eval/runs/{run_id}", status_code=303)


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
        # Load traces for each item
        traces = await run_service.get_traces(session, i.id)
        trace_list = []
        for tr in traces:
            parsed = tr.trace_data
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                parsed = json.loads(tr.trace_data)
            trace_list.append(
                {
                    "trace_type": tr.trace_type,
                    "trace_data": parsed,
                    "created_at": str(tr.created_at) if tr.created_at else None,
                }
            )
        item_data.append(
            {
                "id": i.id,
                "item_index": i.item_index,
                "input_text": (i.input_sent or "")[:200],
                "raw_output": (i.raw_output or "")[:200],
                "overall_pass": i.overall_pass,
                "latency_ms": i.latency_ms,
                "error_message": i.error_message,
                "traces": trace_list,
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


# ── Run Groups ───────────────────────────────────────────────────────────


@router.get("/run-groups", response_class=HTMLResponse)
async def run_group_list(request: Request, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import func, select

    from ..models.run import Run, RunGroup

    exec_type = request.query_params.get("execution_type") or None

    stmt = select(RunGroup).order_by(RunGroup.created_at.desc())
    if exec_type:
        stmt = stmt.where(RunGroup.execution_type == exec_type)
    result = await session.execute(stmt)
    groups = result.scalars().all()

    data = []
    for g in groups:
        # Count runs in group
        count_stmt = select(func.count()).select_from(Run).where(Run.run_group_id == g.id)
        count_result = await session.execute(count_stmt)
        run_count = count_result.scalar() or 0

        tags = []
        if g.tags:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                tags = json.loads(g.tags)

        data.append(
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "execution_type": g.execution_type,
                "scheduled_at": str(g.scheduled_at) if g.scheduled_at else None,
                "tags": tags,
                "run_count": run_count,
                "created_at": str(g.created_at) if g.created_at else None,
            }
        )

    return templates.TemplateResponse(
        "run_groups/list.html",
        {
            "request": request,
            "groups": data,
        },
    )


@router.get("/run-groups/{group_id}", response_class=HTMLResponse)
async def run_group_detail(
    request: Request, group_id: int, session: AsyncSession = Depends(get_session)
):
    from sqlalchemy import select

    from ..models.run import Run, RunGroup

    stmt = select(RunGroup).where(RunGroup.id == group_id)
    result = await session.execute(stmt)
    group = result.scalar_one_or_none()
    if group is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    tags = []
    if group.tags:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            tags = json.loads(group.tags)

    group_data = {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "execution_type": group.execution_type,
        "scheduled_at": str(group.scheduled_at) if group.scheduled_at else None,
        "tags": tags,
        "created_at": str(group.created_at) if group.created_at else None,
    }

    run_stmt = select(Run).where(Run.run_group_id == group_id).order_by(Run.id)
    run_result = await session.execute(run_stmt)
    runs = [_run_to_dict(r) for r in run_result.scalars().all()]

    return templates.TemplateResponse(
        "run_groups/detail.html",
        {
            "request": request,
            "group": group_data,
            "runs": runs,
        },
    )


# ── Comparisons ──────────────────────────────────────────────────────────


@router.get("/comparisons", response_class=HTMLResponse)
async def comparison_page(
    request: Request,
    runs: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    comparison = None
    run_details = []

    if runs:
        from ..services import comparison_service, run_service

        try:
            run_ids = [int(r.strip()) for r in runs.split(",") if r.strip()]
        except ValueError:
            run_ids = []
        if len(run_ids) >= 2:
            comparison = await comparison_service.compare_runs(session, run_ids)
            comparison["run_ids"] = run_ids

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


# ── Search ───────────────────────────────────────────────────────────────


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, session: AsyncSession = Depends(get_session)):
    """Global search across primary entities."""
    from ..services import (
        dataset_service,
        eval_service,
        machine_service,
        runner_service,
        target_service,
    )

    q = (request.query_params.get("q") or "").strip()
    results = {
        "evaluations": [],
        "datasets": [],
        "targets": [],
        "runners": [],
        "machines": [],
    }
    has_results = False

    if q:
        q_lower = q.lower()

        evals = await eval_service.list_evaluations(session)
        results["evaluations"] = [
            _eval_to_dict(e) for e in evals if q_lower in (e.name or "").lower()
        ]

        datasets = await dataset_service.list_datasets(session)
        results["datasets"] = [
            _dataset_to_dict(d)
            for d in datasets
            if q_lower in (d.name or "").lower() or q_lower in (d.source or "").lower()
        ]

        targets = await target_service.list_targets(session)
        results["targets"] = [
            _target_to_dict(t)
            for t in targets
            if q_lower in (t.name or "").lower()
            or q_lower in (t.model_name or "").lower()
            or q_lower in (t.provider or "").lower()
        ]

        runners = await runner_service.list_runners(session)
        results["runners"] = [
            _runner_to_dict(r)
            for r in runners
            if q_lower in (r.name or "").lower() or q_lower in (r.runner_class or "").lower()
        ]

        machines = await machine_service.list_profiles(session)
        results["machines"] = [
            _machine_to_dict(m)
            for m in machines
            if q_lower in (m.hostname or "").lower()
            or q_lower in (m.display_name or "").lower()
            or q_lower in (m.hardware_class or "").lower()
        ]

        has_results = any(v for v in results.values())

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q,
            "results": results,
            "has_results": has_results,
        },
    )


# ── Reports ──────────────────────────────────────────────────────────────


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, session: AsyncSession = Depends(get_session)):
    from ..services import report_service, run_service

    presets = report_service.list_presets()
    preset_data = [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p.get("description", ""),
        }
        for p in presets
    ]

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
    request: Request,
    format: str = "json",
    session: AsyncSession = Depends(get_session),
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
    elif format == "markdown":
        content = report_service.export_markdown({"runs": rows}, title="Eval Report")
        media_type = "text/markdown"
        filename = "eval_report.md"
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


def _runner_to_dict(r) -> dict:
    machine_classes = []
    if r.supported_machine_classes:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            machine_classes = json.loads(r.supported_machine_classes)

    model_families = []
    if r.supported_model_families:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            model_families = json.loads(r.supported_model_families)

    param_surface = None
    if r.parameter_surface:
        try:
            param_surface = json.loads(r.parameter_surface)
        except (json.JSONDecodeError, TypeError):
            param_surface = r.parameter_surface

    return {
        "id": r.id,
        "name": r.name,
        "display_name": r.display_name,
        "runner_class": r.runner_class,
        "version": r.version,
        "default_endpoint_url": r.default_endpoint_url,
        "supported_machine_classes": machine_classes,
        "supported_model_families": model_families,
        "parameter_surface": param_surface,
        "notes": r.notes,
        "is_archived": r.is_archived,
        "created_at": str(r.created_at) if r.created_at else None,
        "updated_at": str(r.updated_at) if r.updated_at else None,
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
