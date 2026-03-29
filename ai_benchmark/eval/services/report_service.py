"""Report generation, presets, and export service."""

from __future__ import annotations

import csv
import html
import io
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from ..models.evaluation import EvaluationVersion
from ..models.run import Run, RunAggregateMetric
from ..models.target import TargetConfiguration

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# In-memory preset storage (will be promoted to DB in a later phase if needed)
_presets: dict[str, dict[str, Any]] = {
    "best_coding_runs": {
        "name": "Best Coding Runs",
        "config": {"group_by": "evaluation", "metrics": ["overall_accuracy", "avg_latency_ms"]},
    },
    "quantization_comparison": {
        "name": "Quantization Comparison",
        "config": {
            "group_by": "model_family",
            "metrics": ["overall_accuracy", "avg_latency_ms", "total_cost_usd"],
        },
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

    if not runs:
        return {"group_by": group_by, "groups": {}, "total_runs": 0}

    run_ids = [r.id for r in runs]

    # Batch-load all metrics for all runs in a single query
    metrics_stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id.in_(run_ids))
    metrics_result = await session.execute(metrics_stmt)
    all_metrics = metrics_result.scalars().all()
    metrics_by_run: dict[int, dict[str, Any]] = {}
    for m in all_metrics:
        metrics_by_run.setdefault(m.run_id, {})[m.metric_name] = m.metric_value

    # Batch-load all target configs for all runs in a single query
    target_ids = {r.target_config_id for r in runs if r.target_config_id is not None}
    targets_by_id: dict[int, Any] = {}
    if target_ids:
        targets_stmt = select(TargetConfiguration).where(TargetConfiguration.id.in_(target_ids))
        targets_result = await session.execute(targets_stmt)
        for tc in targets_result.scalars().all():
            targets_by_id[tc.id] = tc

    summary_rows = []
    for run in runs:
        run_metrics = metrics_by_run.get(run.id, {})
        tc = targets_by_id.get(run.target_config_id)

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

    # Load runner info for runner grouping
    if group_by == "runner":
        from ..models.runner import RunnerProfile

        # Collect all runner_profile_ids from already-loaded targets
        runner_ids = {
            tc.runner_profile_id
            for tc in targets_by_id.values()
            if tc.runner_profile_id is not None
        }
        runners_by_id: dict[int, Any] = {}
        if runner_ids:
            runner_stmt = select(RunnerProfile).where(RunnerProfile.id.in_(runner_ids))
            runner_result = await session.execute(runner_stmt)
            for rp in runner_result.scalars().all():
                runners_by_id[rp.id] = rp

        for row in summary_rows:
            runner_name = "unknown"
            run_obj = next((r for r in runs if r.id == row["run_id"]), None)
            if run_obj:
                tc_obj = targets_by_id.get(run_obj.target_config_id)
                if tc_obj and tc_obj.runner_profile_id:
                    rp = runners_by_id.get(tc_obj.runner_profile_id)
                    if rp:
                        runner_name = rp.name
            row["runner_name"] = runner_name

    # Group results
    groups: dict[str, list] = {}
    for row in summary_rows:
        if group_by == "model_family":
            key = row.get("model_family") or "unknown"
        elif group_by == "machine":
            key = row.get("target_name") or "unknown"
        elif group_by == "runner":
            key = row.get("runner_name") or "unknown"
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


def export_markdown(data: dict, title: str = "Evaluation Report") -> str:
    """Export data as a Markdown document."""
    lines = [f"# {title}", ""]

    # Run metadata
    if "run_id" in data:
        lines.append(f"**Run ID**: {data['run_id']}")
        lines.append(f"**Status**: {data.get('status', 'unknown')}")
        if data.get("model_name"):
            lines.append(f"**Model**: {data['model_name']}")
        if data.get("provider"):
            lines.append(f"**Provider**: {data['provider']}")
        lines.append(
            f"**Items**: {data.get('completed_items', 0)} completed, "
            f"{data.get('failed_items', 0)} failed of {data.get('total_items', 0)}"
        )
        lines.append("")

    # Metrics table
    metrics = data.get("metrics", {})
    if metrics:
        lines.append("## Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for name, value in sorted(metrics.items()):
            lines.append(f"| {name} | {value:.4f} |")
        lines.append("")

    # Items summary
    items = data.get("items", [])
    if items:
        lines.append("## Item Results")
        lines.append("")
        lines.append("| Index | Pass | Latency (ms) | Tokens | Error |")
        lines.append("|---|---|---|---|---|")
        for item in items[:100]:  # Cap at 100 for readability
            if item.get("pass"):
                pass_str = "PASS"
            elif item.get("pass") is False:
                pass_str = "FAIL"
            else:
                pass_str = "-"
            latency = f"{item.get('latency_ms', 0):.0f}" if item.get("latency_ms") else "-"
            tokens = str(item.get("tokens") or "-")
            error = (item.get("error") or "-")[:50]
            idx = item.get("index", "?")
            lines.append(f"| {idx} | {pass_str} | {latency} | {tokens} | {error} |")
        if len(items) > 100:
            lines.append(f"\n*... and {len(items) - 100} more items*")
        lines.append("")

    # Grouped data (from summary reports)
    if "groups" in data:
        lines.append("## Groups")
        lines.append("")
        for group_name, runs in data["groups"].items():
            lines.append(f"### {group_name}")
            lines.append("")
            for run in runs:
                metrics_str = ", ".join(f"{k}: {v:.4f}" for k, v in run.get("metrics", {}).items())
                lines.append(
                    f"- Run {run['run_id']} — {run.get('model_name', '?')} — {metrics_str}"
                )
            lines.append("")

    return "\n".join(lines)


def export_html(data: dict, title: str = "Evaluation Report") -> str:
    """Export data as a standalone HTML document."""
    safe_title = html.escape(title)
    rows_html = ""

    # Single run data
    if "run_id" in data:
        rows_html += "<div class='meta'>"
        rows_html += f"<p><strong>Run ID</strong>: {html.escape(str(data['run_id']))}</p>"
        rows_html += f"<p><strong>Status</strong>: {html.escape(str(data.get('status', '')))}</p>"
        if data.get("model_name"):
            rows_html += f"<p><strong>Model</strong>: {html.escape(str(data['model_name']))}</p>"
        rows_html += "</div>"

    # Metrics
    metrics = data.get("metrics", {})
    if metrics:
        rows_html += "<h2>Metrics</h2><table><tr><th>Metric</th><th>Value</th></tr>"
        for name, value in sorted(metrics.items()):
            rows_html += f"<tr><td>{html.escape(name)}</td><td>{value:.4f}</td></tr>"
        rows_html += "</table>"

    # Items
    items = data.get("items", [])
    if items:
        rows_html += "<h2>Items</h2><table>"
        rows_html += "<tr><th>Index</th><th>Pass</th><th>Latency</th><th>Error</th></tr>"
        for item in items[:200]:
            pass_cls = "pass" if item.get("pass") else "fail"
            pass_text = "PASS" if item.get("pass") else "FAIL"
            latency = f"{item.get('latency_ms', 0):.0f}" if item.get("latency_ms") else "-"
            error = html.escape((item.get("error") or "-")[:80])
            rows_html += (
                f"<tr><td>{item.get('index', '?')}</td>"
                f"<td class='{pass_cls}'>{pass_text}</td>"
                f"<td>{latency}</td><td>{error}</td></tr>"
            )
        rows_html += "</table>"

    # Grouped data
    if "groups" in data:
        for group_name, runs in data["groups"].items():
            rows_html += f"<h3>{html.escape(str(group_name))}</h3><ul>"
            for run in runs:
                metrics_str = ", ".join(
                    f"{html.escape(k)}: {v:.4f}" for k, v in run.get("metrics", {}).items()
                )
                model = html.escape(str(run.get("model_name", "?")))
                rows_html += f"<li>Run {run['run_id']} — {model} — {metrics_str}</li>"
            rows_html += "</ul>"

    return f"""<!DOCTYPE html>
<html><head><title>{safe_title}</title>
<style>body{{font-family:sans-serif;max-width:960px;margin:0 auto;padding:20px}}
h1{{color:#333}}h2{{color:#444;margin-top:24px}}h3{{color:#555}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left}}
th{{background:#f5f5f5}}.pass{{color:#2a7;font-weight:bold}}
.fail{{color:#c33;font-weight:bold}}.meta p{{margin:4px 0}}
li{{margin:4px 0}}</style>
</head><body><h1>{safe_title}</h1>{rows_html}</body></html>"""
