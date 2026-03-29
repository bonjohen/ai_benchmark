"""Run lifecycle routes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from ...execution.orchestrator import RunOrchestrator
from ...services import run_service
from ..app import get_session
from ..schemas.run import (
    RescoreRequest,
    RunBatchCreate,
    RunCreate,
    RunItemResultResponse,
    RunMetricResponse,
    RunResponse,
)
from ..serializers import run_to_dict as _run_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
        session,
        status=status,
        evaluation_id=evaluation_id,
        target_id=target_id,
        model_name=model_name,
        limit=limit,
        offset=offset,
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


@router.post("/batch", status_code=201)
async def create_batch(
    body: RunBatchCreate,
    session: AsyncSession = Depends(get_session),
):
    # Look up dataset_version_id and item count from evaluation version
    from ...models.dataset import DatasetVersion
    from ...models.evaluation import EvaluationVersion

    ev = await session.get(EvaluationVersion, body.evaluation_version_id)
    if ev is None:
        raise HTTPException(404, f"EvaluationVersion {body.evaluation_version_id} not found")

    # Compute total_items from the dataset version's item_count
    total_items = 0
    dv = await session.get(DatasetVersion, ev.dataset_version_id)
    if dv is not None:
        total_items = dv.item_count

    rg, runs = await run_service.create_batch(
        session,
        evaluation_version_id=body.evaluation_version_id,
        target_config_ids=body.target_config_ids,
        dataset_version_id=ev.dataset_version_id,
        execution_type=body.execution_type,
        name=body.name,
        machine_profile_id=body.machine_profile_id,
        total_items=total_items,
    )
    result = {"group_id": rg.id, "runs": [_run_to_dict(r) for r in runs]}
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
        session,
        run_id,
        passed=passed,
        limit=limit,
        offset=offset,
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
    return [
        {
            "id": a.id,
            "run_id": a.run_id,
            "artifact_type": a.artifact_type,
            "file_path": a.file_path,
            "created_at": str(a.created_at),
        }
        for a in artifacts
    ]


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        run = await run_service.cancel_run(session, run_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
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


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Resume a failed or partially completed run."""
    run = await run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    if run.status not in ("failed", "partially_completed"):
        raise HTTPException(
            400,
            f"Cannot resume run in {run.status} state",
        )
    await run_service.update_status(session, run_id, "queued")
    run = await run_service.get_run(session, run_id)
    result = _run_to_dict(run)
    await session.commit()
    return result


@router.get("/{run_id}/items/{item_id}/traces")
async def get_item_traces(
    run_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Get trace references for a specific item result."""
    traces = await run_service.get_traces(session, item_id)
    return [
        {
            "id": t.id,
            "run_item_result_id": t.run_item_result_id,
            "trace_type": t.trace_type,
            "trace_data": json.loads(t.trace_data) if t.trace_data else None,
            "created_at": str(t.created_at),
        }
        for t in traces
    ]


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
