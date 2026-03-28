"""Report generation, presets, and export service."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.evaluation import EvaluationVersion
from ..models.run import Run, RunAggregateMetric
from ..models.target import TargetConfiguration

# In-memory preset storage (will be promoted to DB in a later phase if needed)
_presets: dict[str, dict[str, Any]] = {
    "best_coding_runs": {
        "name": "Best Coding Runs",
        "config": {"group_by": "evaluation", "metrics": ["overall_accuracy", "avg_latency_ms"]},
    },
    "quantization_comparison": {
        "name": "Quantization Comparison",
        "config": {"group_by": "model_family", "metrics": ["overall_accuracy", "avg_latency_ms", "total_cost_usd"]},
    },
    "standard_laptop_viability": {
        "name": "Standard Laptop Viability",
        "config": {"group_by": "machine", "filters": {"hardware_class": "standard_laptop"}},
    },
    "older_hardware_baseline": {
        "name": "Older Hardware Baseline",
        "config": {"group_by": "machine", "filters": {"hardware_class": "gtx_1060_laptop"}},
    },
}


async def generate_summary(
    session: AsyncSession,
    *,
    group_by: str = "evaluation",
    filters: dict | None = None,
    metrics: list[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Generate a summary report grouped by evaluation, model_family, machine, or date_range."""
    filters = filters or {}
    stmt = select(Run).where(Run.status.in_(["completed", "partially_completed"]))
    if filters.get("evaluation_id"):
        ev_ids_stmt = select(EvaluationVersion.id).where(
            EvaluationVersion.evaluation_id == filters["evaluation_id"]
        )
        ev_result = await session.execute(ev_ids_stmt)
        ev_ids = list(ev_result.scalars().all())
        stmt = stmt.where(Run.evaluation_version_id.in_(ev_ids))
    stmt = stmt.order_by(Run.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    # Load metrics for each run
    summary_rows = []
    for run in runs:
        metrics_stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run.id)
        metrics_result = await session.execute(metrics_stmt)
        run_metrics = {m.metric_name: m.metric_value for m in metrics_result.scalars().all()}

        # Load target info for grouping
        tc = await session.get(TargetConfiguration, run.target_config_id)

        row = {
            "run_id": run.id,
            "status": run.status,
            "model_name": tc.model_name if tc else None,
            "model_family": tc.model_family if tc else None,
            "provider": tc.provider if tc else None,
            "target_name": tc.name if tc else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "metrics": run_metrics,
        }
        summary_rows.append(row)

    # Group results
    groups: dict[str, list] = {}
    for row in summary_rows:
        if group_by == "model_family":
            key = row.get("model_family") or "unknown"
        elif group_by == "machine":
            key = row.get("target_name") or "unknown"
        else:
            key = str(row["run_id"])
        groups.setdefault(key, []).append(row)

    return {"group_by": group_by, "groups": groups, "total_runs": len(runs)}


def list_presets() -> list[dict[str, Any]]:
    return [{"id": k, **v} for k, v in _presets.items()]


def save_preset(preset_id: str, name: str, config: dict) -> dict[str, Any]:
    _presets[preset_id] = {"name": name, "config": config}
    return {"id": preset_id, "name": name, "config": config}


async def run_preset(session: AsyncSession, preset_id: str) -> dict[str, Any]:
    preset = _presets.get(preset_id)
    if preset is None:
        raise ValueError(f"Preset '{preset_id}' not found")
    config = preset["config"]
    return await generate_summary(
        session,
        group_by=config.get("group_by", "evaluation"),
        filters=config.get("filters"),
        metrics=config.get("metrics"),
    )


def export_json(data: dict | list) -> str:
    return json.dumps(data, indent=2, default=str)


def export_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        # Flatten nested dicts for CSV
        flat = {}
        for k, v in row.items():
            flat[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
        writer.writerow(flat)
    return output.getvalue()


def export_html(data: dict, title: str = "Evaluation Report") -> str:
    rows_html = ""
    if "groups" in data:
        for group_name, runs in data["groups"].items():
            rows_html += f"<h3>{group_name}</h3><ul>"
            for run in runs:
                metrics_str = ", ".join(
                    f"{k}: {v:.4f}" for k, v in run.get("metrics", {}).items()
                )
                rows_html += f"<li>Run {run['run_id']} — {run.get('model_name', '?')} — {metrics_str}</li>"
            rows_html += "</ul>"

    return f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>body{{font-family:sans-serif;max-width:960px;margin:0 auto;padding:20px}}
h1{{color:#333}}h3{{color:#555}}li{{margin:4px 0}}</style>
</head><body><h1>{title}</h1>{rows_html}</body></html>"""
