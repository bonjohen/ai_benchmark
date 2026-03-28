"""Side-by-side run comparison and config diff service."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.run import Run, RunAggregateMetric, RunItemResult
from ..models.target import TargetConfiguration


async def compare_runs(
    session: AsyncSession,
    run_ids: list[int],
) -> dict[str, Any]:
    """Compare N runs: aggregate metric deltas, per-scorer breakdown, item-level diffs."""
    runs: list[Run] = []
    metrics_by_run: dict[int, dict[str, float]] = {}
    items_by_run: dict[int, dict[int, RunItemResult]] = {}

    for run_id in run_ids:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        runs.append(run)

        # Load aggregate metrics
        stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run_id)
        result = await session.execute(stmt)
        metrics_by_run[run_id] = {
            m.metric_name: m.metric_value for m in result.scalars().all()
        }

        # Load item results keyed by test_case_id
        stmt = select(RunItemResult).where(RunItemResult.run_id == run_id)
        result = await session.execute(stmt)
        items_by_run[run_id] = {
            item.test_case_id: item for item in result.scalars().all()
        }

    # Compute metric deltas (relative to first run)
    all_metric_names = set()
    for m in metrics_by_run.values():
        all_metric_names.update(m.keys())

    metric_comparison = []
    base_run_id = run_ids[0]
    for name in sorted(all_metric_names):
        entry: dict[str, Any] = {"metric": name}
        base_value = metrics_by_run[base_run_id].get(name)
        for run_id in run_ids:
            value = metrics_by_run[run_id].get(name)
            entry[f"run_{run_id}"] = value
            if base_value is not None and value is not None and run_id != base_run_id:
                entry[f"delta_{run_id}"] = round(value - base_value, 6)
        metric_comparison.append(entry)

    # Per-scorer breakdown from aggregate metrics
    scorer_metrics = [m for m in metric_comparison if m["metric"].startswith("scorer:")]

    # Item-level diffs for shared test cases
    all_test_case_ids = set()
    for items in items_by_run.values():
        all_test_case_ids.update(items.keys())

    item_diffs = []
    for tc_id in sorted(all_test_case_ids):
        diff_entry: dict[str, Any] = {"test_case_id": tc_id}
        outputs = {}
        passes = {}
        for run_id in run_ids:
            item = items_by_run[run_id].get(tc_id)
            if item:
                outputs[run_id] = item.raw_output
                passes[run_id] = item.overall_pass

        diff_entry["outputs"] = outputs
        diff_entry["passes"] = passes

        # Flag disagreements
        pass_values = [v for v in passes.values() if v is not None]
        diff_entry["disagree"] = len(set(pass_values)) > 1 if pass_values else False
        item_diffs.append(diff_entry)

    return {
        "run_ids": run_ids,
        "metric_comparison": metric_comparison,
        "scorer_breakdown": scorer_metrics,
        "item_diffs": item_diffs,
        "disagreement_count": sum(1 for d in item_diffs if d["disagree"]),
    }


async def diff_target_configs(
    session: AsyncSession,
    target_ids: list[int],
) -> dict[str, Any]:
    """Field-level comparison of 2+ target configurations. Returns only differing fields."""
    targets: list[TargetConfiguration] = []
    for tid in target_ids:
        t = await session.get(TargetConfiguration, tid)
        if t is None:
            raise ValueError(f"TargetConfiguration {tid} not found")
        targets.append(t)

    compare_fields = [
        "model_name", "model_family", "provider", "endpoint_url",
        "machine_profile_id", "runtime_backend", "prompt_wrapper",
        "inference_params", "runtime_options",
    ]

    diffs: dict[str, dict[int, Any]] = {}
    for field in compare_fields:
        values = {}
        for t in targets:
            val = getattr(t, field)
            # Parse JSON fields for readable comparison
            if field in ("inference_params", "runtime_options") and val:
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            values[t.id] = val

        # Only include if values differ
        unique_vals = set(json.dumps(v, sort_keys=True, default=str) for v in values.values())
        if len(unique_vals) > 1:
            diffs[field] = values

    return {
        "target_ids": target_ids,
        "target_names": {t.id: t.name for t in targets},
        "differing_fields": diffs,
        "identical_fields": [f for f in compare_fields if f not in diffs],
    }
