"""Run lifecycle management service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.run import Run, RunAggregateMetric, RunGroup, RunItemResult
from . import machine_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_run(
    session: AsyncSession,
    *,
    evaluation_version_id: int,
    target_config_id: int,
    dataset_version_id: int,
    trigger_type: str = "manual",
    priority: int = 0,
    total_items: int = 0,
    machine_profile_id: int | None = None,
    run_group_id: int | None = None,
) -> Run:
    """Create a run, optionally capturing a machine snapshot."""
    machine_snapshot_id = None
    if machine_profile_id:
        snap = await machine_service.capture_snapshot(session, machine_profile_id)
        machine_snapshot_id = snap.id

    run = Run(
        run_group_id=run_group_id,
        evaluation_version_id=evaluation_version_id,
        target_config_id=target_config_id,
        machine_snapshot_id=machine_snapshot_id,
        dataset_version_id=dataset_version_id,
        status="queued",
        trigger_type=trigger_type,
        priority=priority,
        total_items=total_items,
    )
    session.add(run)
    await session.flush()
    return run


async def create_batch(
    session: AsyncSession,
    *,
    evaluation_version_id: int,
    target_config_ids: list[int],
    dataset_version_id: int,
    execution_type: str = "batch",
    name: str | None = None,
    machine_profile_id: int | None = None,
    total_items: int = 0,
) -> tuple[RunGroup, list[Run]]:
    """Create a RunGroup with N runs for batch/matrix execution."""
    rg = RunGroup(name=name, execution_type=execution_type)
    session.add(rg)
    await session.flush()

    runs = []
    for target_id in target_config_ids:
        run = await create_run(
            session,
            evaluation_version_id=evaluation_version_id,
            target_config_id=target_id,
            dataset_version_id=dataset_version_id,
            trigger_type="matrix" if execution_type == "matrix" else "api",
            machine_profile_id=machine_profile_id,
            run_group_id=rg.id,
            total_items=total_items,
        )
        runs.append(run)

    return rg, runs


async def get_run(session: AsyncSession, run_id: int) -> Run | None:
    return await session.get(Run, run_id)


async def list_runs(
    session: AsyncSession,
    *,
    evaluation_id: int | None = None,
    target_id: int | None = None,
    status: str | None = None,
    model_name: str | None = None,
    hardware_class: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
    stmt = select(Run)
    if evaluation_id:
        from ..models.evaluation import EvaluationVersion

        ev_ids_stmt = select(EvaluationVersion.id).where(
            EvaluationVersion.evaluation_id == evaluation_id
        )
        ev_result = await session.execute(ev_ids_stmt)
        ev_ids = list(ev_result.scalars().all())
        stmt = stmt.where(Run.evaluation_version_id.in_(ev_ids))
    if target_id:
        stmt = stmt.where(Run.target_config_id == target_id)
    if status:
        stmt = stmt.where(Run.status == status)
    if date_from:
        stmt = stmt.where(Run.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Run.created_at <= date_to)
    stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    # Post-query filters requiring target config lookup
    if model_name or hardware_class:
        from ..models.machine import MachineProfile
        from ..models.target import TargetConfiguration

        filtered = []
        for run in runs:
            tc = await session.get(TargetConfiguration, run.target_config_id)
            if model_name and not tc.model_name.lower().startswith(model_name.lower()):
                continue
            if hardware_class and tc.machine_profile_id:
                mp = await session.get(MachineProfile, tc.machine_profile_id)
                if mp.hardware_class != hardware_class:
                    continue
            elif hardware_class:
                continue
            filtered.append(run)
        return filtered

    return runs


async def update_status(
    session: AsyncSession,
    run_id: int,
    status: str,
    *,
    error_message: str | None = None,
) -> Run | None:
    run = await session.get(Run, run_id)
    if run is None:
        return None
    run.status = status
    now = datetime.now(UTC)
    if status in ("running", "running_generation") and run.started_at is None:
        run.started_at = now
    elif status in ("scoring", "running_scorers"):
        run.scoring_started_at = now
    elif status in ("completed", "failed", "canceled", "partially_completed"):
        run.completed_at = now
    if error_message:
        run.error_message = error_message
    await session.flush()
    await session.refresh(run)
    return run


async def cancel_run(session: AsyncSession, run_id: int) -> Run | None:
    run = await session.get(Run, run_id)
    if run is None:
        return None
    if run.status in ("completed", "failed", "canceled"):
        raise ValueError(f"Cannot cancel run in {run.status} state")
    return await update_status(session, run_id, "canceled")


async def get_item_results(
    session: AsyncSession,
    run_id: int,
    *,
    passed: bool | None = None,
    min_latency: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RunItemResult]:
    stmt = (
        select(RunItemResult)
        .where(RunItemResult.run_id == run_id)
        .order_by(RunItemResult.item_index)
    )
    if passed is not None:
        stmt = stmt.where(RunItemResult.overall_pass == passed)
    if min_latency is not None:
        stmt = stmt.where(RunItemResult.latency_ms >= min_latency)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_metrics(session: AsyncSession, run_id: int) -> list[RunAggregateMetric]:
    stmt = (
        select(RunAggregateMetric)
        .where(RunAggregateMetric.run_id == run_id)
        .order_by(RunAggregateMetric.metric_name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_artifacts(session: AsyncSession, run_id: int):
    from ..models.artifact import Artifact

    stmt = select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def rescore_run(
    session: AsyncSession,
    run_id: int,
    scorer_config: list[dict],
) -> Run | None:
    """Rescore a run with a new scorer configuration.

    Updates the EvaluationVersion's scorer_config, re-invokes the scorer runner
    on stored outputs (no regeneration), and recomputes aggregate metrics.
    """
    import json

    run = await session.get(Run, run_id)
    if run is None:
        return None

    from ..models.evaluation import EvaluationVersion

    ev = await session.get(EvaluationVersion, run.evaluation_version_id)
    if ev is None:
        raise ValueError(f"EvaluationVersion {run.evaluation_version_id} not found")

    # Update scorer config on the version
    ev.scorer_config = json.dumps(scorer_config)
    await session.flush()

    # Re-score using ScorerRunner (reuses stored raw_output)
    from ..scoring.scorer_runner import ScorerRunner

    runner = ScorerRunner()
    await runner.score_run(session, run_id)
    await runner.compute_aggregates(session, run_id)

    # Determine new terminal status
    scored_stmt = select(RunItemResult).where(RunItemResult.run_id == run_id)
    result = await session.execute(scored_stmt)
    items = list(result.scalars().all())

    passed_count = sum(1 for i in items if i.overall_pass is True)
    failed_count = sum(1 for i in items if i.overall_pass is False)

    if failed_count == 0 and passed_count > 0:
        run.status = "completed"
    elif passed_count == 0 and failed_count > 0:
        run.status = "failed"
    elif passed_count > 0 and failed_count > 0:
        run.status = "partially_completed"

    await session.flush()
    await session.refresh(run)
    return run


async def get_traces(
    session: AsyncSession,
    run_item_result_id: int,
) -> list:
    """Fetch all trace references for a specific item result."""
    from ..models.trace import TraceReference

    stmt = (
        select(TraceReference)
        .where(TraceReference.run_item_result_id == run_item_result_id)
        .order_by(TraceReference.trace_type)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
