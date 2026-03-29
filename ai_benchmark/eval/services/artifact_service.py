"""Artifact generation, storage, and retention management."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..config import EvalSettings
from ..models.artifact import Artifact
from ..models.run import Run, RunAggregateMetric, RunItemResult
from ..models.target import TargetConfiguration
from . import report_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


def _artifact_dir(settings: EvalSettings | None = None) -> Path:
    """Return the artifact storage directory, creating it if needed."""
    settings = settings or EvalSettings()
    path = Path(settings.artifact_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def generate_run_artifacts(
    session: AsyncSession,
    run_id: int,
    *,
    formats: list[str] | None = None,
    settings: EvalSettings | None = None,
) -> list[Artifact]:
    """Generate export artifacts for a completed run.

    Supported formats: json, csv, markdown, html.
    Defaults to all four if not specified.
    """
    formats = formats or ["json", "csv", "markdown", "html"]
    settings = settings or EvalSettings()
    base_dir = _artifact_dir(settings) / f"run_{run_id}"
    base_dir.mkdir(parents=True, exist_ok=True)

    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    # Load item results and metrics
    stmt = (
        select(RunItemResult)
        .where(RunItemResult.run_id == run_id)
        .order_by(RunItemResult.item_index)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    metrics_stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run_id)
    metrics_result = await session.execute(metrics_stmt)
    metrics = {m.metric_name: m.metric_value for m in metrics_result.scalars().all()}

    # Load target info
    tc = await session.get(TargetConfiguration, run.target_config_id)

    data = _build_export_data(run, items, metrics, tc)
    artifacts: list[Artifact] = []

    for fmt in formats:
        content, filename, mime_type = _render_format(fmt, data, run_id)
        file_path = base_dir / filename
        file_path.write_text(content, encoding="utf-8")

        artifact = Artifact(
            run_id=run_id,
            artifact_type=f"export_{fmt}",
            filename=filename,
            file_path=str(file_path),
            size_bytes=file_path.stat().st_size,
            mime_type=mime_type,
        )
        session.add(artifact)
        artifacts.append(artifact)

    await session.flush()
    logger.info("artifacts_generated", run_id=run_id, count=len(artifacts))
    return artifacts


async def store_execution_log(
    session: AsyncSession,
    run_id: int,
    log_content: str,
    *,
    settings: EvalSettings | None = None,
) -> Artifact:
    """Store an execution log as a separate artifact."""
    settings = settings or EvalSettings()
    base_dir = _artifact_dir(settings) / f"run_{run_id}" / "logs"
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"execution_log_{timestamp}.txt"
    file_path = base_dir / filename
    file_path.write_text(log_content, encoding="utf-8")

    artifact = Artifact(
        run_id=run_id,
        artifact_type="execution_log",
        filename=filename,
        file_path=str(file_path),
        size_bytes=file_path.stat().st_size,
        mime_type="text/plain",
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def generate_comparison_bundle(
    session: AsyncSession,
    run_ids: list[int],
    *,
    settings: EvalSettings | None = None,
) -> Artifact | None:
    """Generate a comparison bundle artifact for multiple runs."""
    if len(run_ids) < 2:
        return None

    settings = settings or EvalSettings()
    base_dir = _artifact_dir(settings) / "comparisons"
    base_dir.mkdir(parents=True, exist_ok=True)

    runs_data = []
    for rid in run_ids:
        run = await session.get(Run, rid)
        if run is None:
            continue
        stmt = (
            select(RunItemResult)
            .where(RunItemResult.run_id == rid)
            .order_by(RunItemResult.item_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        metrics_stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == rid)
        metrics_result = await session.execute(metrics_stmt)
        metrics = {m.metric_name: m.metric_value for m in metrics_result.scalars().all()}

        tc = await session.get(TargetConfiguration, run.target_config_id)
        runs_data.append(_build_export_data(run, items, metrics, tc))

    bundle = {
        "comparison_type": "side_by_side",
        "run_ids": run_ids,
        "generated_at": datetime.now(UTC).isoformat(),
        "runs": runs_data,
    }

    ids_str = "_".join(str(r) for r in run_ids)
    filename = f"comparison_{ids_str}.json"
    file_path = base_dir / filename
    file_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")

    # Use first run_id as the parent
    artifact = Artifact(
        run_id=run_ids[0],
        artifact_type="comparison_bundle",
        filename=filename,
        file_path=str(file_path),
        size_bytes=file_path.stat().st_size,
        mime_type="application/json",
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def cleanup_artifacts(
    session: AsyncSession,
    *,
    max_age_days: int = 90,
    max_artifacts_per_run: int = 20,
    settings: EvalSettings | None = None,
) -> int:
    """Remove artifacts older than max_age_days and enforce per-run limits.

    Returns count of artifacts removed.
    """
    removed = 0
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

    # Remove old artifacts
    stmt = select(Artifact).where(Artifact.created_at < cutoff)
    result = await session.execute(stmt)
    old_artifacts = list(result.scalars().all())

    for artifact in old_artifacts:
        _delete_artifact_file(artifact)
        await session.delete(artifact)
        removed += 1

    # Enforce per-run limits (keep newest)
    runs_stmt = select(Artifact.run_id).group_by(Artifact.run_id)
    runs_result = await session.execute(runs_stmt)
    run_ids = [r[0] for r in runs_result.all()]

    for rid in run_ids:
        stmt = (
            select(Artifact)
            .where(Artifact.run_id == rid)
            .order_by(Artifact.created_at.desc())
            .offset(max_artifacts_per_run)
        )
        result = await session.execute(stmt)
        excess = list(result.scalars().all())
        for artifact in excess:
            _delete_artifact_file(artifact)
            await session.delete(artifact)
            removed += 1

    await session.flush()
    if removed:
        logger.info("artifacts_cleaned", removed=removed)
    return removed


async def cleanup_traces(
    session: AsyncSession,
    *,
    max_age_days: int = 90,
) -> int:
    """Remove trace references older than max_age_days.

    Returns count of traces removed.
    """
    from ..models.trace import TraceReference

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    stmt = select(TraceReference).where(TraceReference.created_at < cutoff)
    result = await session.execute(stmt)
    old_traces = list(result.scalars().all())

    for trace in old_traces:
        await session.delete(trace)

    await session.flush()
    if old_traces:
        logger.info("traces_cleaned", removed=len(old_traces))
    return len(old_traces)


async def cleanup_raw_outputs(
    session: AsyncSession,
    *,
    max_age_days: int = 90,
) -> int:
    """Null out raw_output on item results older than max_age_days.

    Preserves normalized_output and scorer_results for historical analysis
    while removing potentially sensitive raw model outputs.
    Returns count of items cleaned.
    """
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

    # Find runs older than cutoff
    run_stmt = select(Run.id).where(Run.completed_at < cutoff)
    run_result = await session.execute(run_stmt)
    old_run_ids = [r[0] for r in run_result.all()]

    if not old_run_ids:
        return 0

    cleaned = 0
    for rid in old_run_ids:
        item_stmt = select(RunItemResult).where(
            RunItemResult.run_id == rid,
            RunItemResult.raw_output.isnot(None),
        )
        item_result = await session.execute(item_stmt)
        for item in item_result.scalars().all():
            item.raw_output = None
            cleaned += 1

    await session.flush()
    if cleaned:
        logger.info("raw_outputs_cleaned", removed=cleaned, runs=len(old_run_ids))
    return cleaned


async def run_retention_cleanup(
    session: AsyncSession,
    *,
    artifact_max_age_days: int = 90,
    artifact_max_per_run: int = 20,
    trace_max_age_days: int = 90,
    output_max_age_days: int = 90,
    settings: EvalSettings | None = None,
) -> dict:
    """Run all retention cleanup tasks. Returns summary of what was removed."""
    artifacts_removed = await cleanup_artifacts(
        session,
        max_age_days=artifact_max_age_days,
        max_artifacts_per_run=artifact_max_per_run,
        settings=settings,
    )
    traces_removed = await cleanup_traces(session, max_age_days=trace_max_age_days)
    outputs_cleaned = await cleanup_raw_outputs(session, max_age_days=output_max_age_days)

    return {
        "artifacts_removed": artifacts_removed,
        "traces_removed": traces_removed,
        "outputs_cleaned": outputs_cleaned,
    }


def _delete_artifact_file(artifact: Artifact) -> None:
    """Delete the physical file backing an artifact, if it exists."""
    try:
        if artifact.file_path and os.path.exists(artifact.file_path):
            os.remove(artifact.file_path)
    except OSError:
        logger.warning("artifact_file_delete_failed", path=artifact.file_path)


def _build_export_data(
    run: Run,
    items: list[RunItemResult],
    metrics: dict[str, float],
    tc: TargetConfiguration | None,
) -> dict:
    """Build the standard export data dict for a run."""
    return {
        "run_id": run.id,
        "status": run.status,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
        "failed_items": run.failed_items,
        "model_name": tc.model_name if tc else None,
        "provider": tc.provider if tc else None,
        "target_name": tc.name if tc else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "metrics": metrics,
        "items": [
            {
                "index": i.item_index,
                "input": i.input_sent[:200] if i.input_sent else "",
                "raw_output": i.raw_output,
                "normalized_output": i.normalized_output,
                "pass": i.overall_pass,
                "latency_ms": i.latency_ms,
                "tokens": i.total_tokens,
                "cost_usd": i.cost_estimate_usd,
                "error": i.error_message,
                "retry_count": i.retry_count,
            }
            for i in items
        ],
    }


def _render_format(fmt: str, data: dict, run_id: int) -> tuple[str, str, str]:
    """Render export data into a specific format. Returns (content, filename, mime_type)."""
    if fmt == "json":
        return (
            report_service.export_json(data),
            f"run_{run_id}.json",
            "application/json",
        )
    elif fmt == "csv":
        return (
            report_service.export_csv(data.get("items", [])),
            f"run_{run_id}.csv",
            "text/csv",
        )
    elif fmt == "markdown":
        return (
            report_service.export_markdown(data, title=f"Run {run_id}"),
            f"run_{run_id}.md",
            "text/markdown",
        )
    elif fmt == "html":
        return (
            report_service.export_html(data, title=f"Run {run_id}"),
            f"run_{run_id}.html",
            "text/html",
        )
    else:
        raise ValueError(f"Unsupported format: {fmt}")
