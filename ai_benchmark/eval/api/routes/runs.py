"""Run lifecycle routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import get_session
from ..schemas.run import (
    RescoreRequest,
    RunBatchCreate,
    RunCreate,
    RunItemResultResponse,
    RunMetricResponse,
    RunResponse,
)
from ...services import run_service
from ...execution.orchestrator import RunOrchestrator

router = APIRouter()


@router.get("", response_model=list[RunResponse])
async def list_runs(
    status: str | None = None,
    evaluation_id: int | None = None,
    target_id: int | None = None,
    model_name: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    runs = await run_service.list_runs(
        session, status=status, evaluation_id=evaluation_id,
        target_id=target_id, model_name=model_name,
        limit=limit, offset=offset,
    )
    return [_run_to_dict(r) for r in runs]


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreate,
    session: AsyncSession = Depends(get_session),
):
    orch = RunOrchestrator()
    run = await orch.create_run(
        session,
        evaluation_version_id=body.evaluation_version_id,
        target_config_id=body.target_config_id,
        trigger_type=body.trigger_type,
        priority=body.priority,
        machine_profile_id=body.machine_profile_id,
    )
    result = _run_to_dict(run)

    await session.commit()

    return result


@router.post("/batch", response_model=list[RunResponse], status_code=201)
async def create_batch(
    body: RunBatchCreate,
    session: AsyncSession = Depends(get_session),
):
    rg, runs = await run_service.create_batch(
        session,
        evaluation_version_id=body.evaluation_version_id,
        target_config_ids=body.target_config_ids,
        execution_type=body.execution_type,
        name=body.name,
        machine_profile_id=body.machine_profile_id,
    )
    result = [_run_to_dict(r) for r in runs]
    await session.commit()
    return result


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    run = await run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return _run_to_dict(run)


@router.get("/{run_id}/items", response_model=list[RunItemResultResponse])
async def list_items(
    run_id: int,
    passed: bool | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items = await run_service.get_item_results(
        session, run_id, passed=passed, limit=limit, offset=offset,
    )
    return [_item_to_dict(i) for i in items]


@router.get("/{run_id}/items/{item_index}", response_model=RunItemResultResponse)
async def get_item(
    run_id: int,
    item_index: int,
    session: AsyncSession = Depends(get_session),
):
    items = await run_service.get_item_results(session, run_id, limit=1, offset=item_index)
    if not items:
        raise HTTPException(404, "Item not found")
    return _item_to_dict(items[0])


@router.get("/{run_id}/metrics", response_model=list[RunMetricResponse])
async def get_metrics(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    metrics = await run_service.get_metrics(session, run_id)
    return [_metric_to_dict(m) for m in metrics]


@router.get("/{run_id}/artifacts")
async def list_artifacts(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    artifacts = await run_service.list_artifacts(session, run_id)
    return [{"id": a.id, "run_id": a.run_id, "artifact_type": a.artifact_type,
             "file_path": a.file_path, "created_at": str(a.created_at)} for a in artifacts]


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        run = await run_service.cancel_run(session, run_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if run is None:
        raise HTTPException(404, "Run not found")
    result = _run_to_dict(run)

    await session.commit()

    return result


@router.post("/{run_id}/retry", response_model=RunResponse, status_code=201)
async def retry_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    old_run = await run_service.get_run(session, run_id)
    if old_run is None:
        raise HTTPException(404, "Run not found")
    orch = RunOrchestrator()
    new_run = await orch.create_run(
        session,
        evaluation_version_id=old_run.evaluation_version_id,
        target_config_id=old_run.target_config_id,
        trigger_type="retry",
    )
    result = _run_to_dict(new_run)

    await session.commit()

    return result


@router.post("/{run_id}/rescore", response_model=RunResponse)
async def rescore_run(
    run_id: int,
    body: RescoreRequest,
    session: AsyncSession = Depends(get_session),
):
    run = await run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")

    # Update the evaluation version scorer config and re-score
    from ...models.evaluation import EvaluationVersion
    ev = await session.get(EvaluationVersion, run.evaluation_version_id)
    if ev:
        ev.scorer_config = json.dumps(body.scorer_config)
        await session.flush()

    orch = RunOrchestrator()
    run = await orch.score_run(session, run_id)
    result = _run_to_dict(run)

    await session.commit()

    return result


def _run_to_dict(r) -> dict:
    return {
        "id": r.id,
        "run_group_id": r.run_group_id,
        "evaluation_version_id": r.evaluation_version_id,
        "target_config_id": r.target_config_id,
        "machine_snapshot_id": r.machine_snapshot_id,
        "dataset_version_id": r.dataset_version_id,
        "status": r.status,
        "trigger_type": r.trigger_type,
        "priority": r.priority,
        "started_at": r.started_at,
        "scoring_started_at": r.scoring_started_at,
        "completed_at": r.completed_at,
        "error_message": r.error_message,
        "total_items": r.total_items,
        "completed_items": r.completed_items,
        "failed_items": r.failed_items,
        "skipped_items": r.skipped_items,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _item_to_dict(i) -> dict:
    return {
        "id": i.id,
        "run_id": i.run_id,
        "test_case_id": i.test_case_id,
        "item_index": i.item_index,
        "input_sent": i.input_sent,
        "raw_output": i.raw_output,
        "normalized_output": i.normalized_output,
        "scorer_results": json.loads(i.scorer_results) if i.scorer_results else None,
        "overall_pass": i.overall_pass,
        "error_message": i.error_message,
        "latency_ms": i.latency_ms,
        "prompt_tokens": i.prompt_tokens,
        "completion_tokens": i.completion_tokens,
        "total_tokens": i.total_tokens,
        "cost_estimate_usd": i.cost_estimate_usd,
        "retry_count": i.retry_count,
        "trace_id": i.trace_id,
        "started_at": i.started_at,
        "completed_at": i.completed_at,
    }


def _metric_to_dict(m) -> dict:
    return {
        "id": m.id,
        "run_id": m.run_id,
        "metric_name": m.metric_name,
        "metric_value": m.metric_value,
        "metric_metadata": json.loads(m.metric_metadata) if m.metric_metadata else None,
        "created_at": m.created_at,
    }
