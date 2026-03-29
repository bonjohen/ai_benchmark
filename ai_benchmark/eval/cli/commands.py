"""Eval CLI commands — run, status, compare, export, serve."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from ...models.base import Base, create_engine, create_session_factory


def _get_eval_engine(settings):
    """Create engine with eval models registered."""
    engine = create_engine(settings.database_url)
    # Import all models
    from ...models import events, research, sources  # noqa: F401
    from ..models import artifact, dataset, evaluation, machine, run, scorer, target  # noqa: F401

    return engine


@click.group("eval")
def eval_group():
    """Model evaluation pipeline commands."""
    pass


@eval_group.command("run")
@click.option("--evaluation", required=True, help="Evaluation name or ID.")
@click.option("--target", required=True, help="Target config name or ID.")
@click.option("--priority", default=0, help="Run priority.")
@click.pass_context
def run_eval(ctx: click.Context, evaluation: str, target: str, priority: int):
    """Execute an evaluation run."""
    settings = ctx.obj["settings"]

    async def _run():
        engine = _get_eval_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from ..execution.orchestrator import RunOrchestrator

            # Resolve names to IDs
            ev_id = await _resolve_eval(session, evaluation)
            tc_id = await _resolve_target(session, target)

            orch = RunOrchestrator()
            run = await orch.create_run(
                session,
                evaluation_version_id=ev_id,
                target_config_id=tc_id,
                priority=priority,
            )
            click.echo(f"Run {run.id} created (status: {run.status})")

            run = await orch.execute_run(session, run.id)
            click.echo(
                f"Execution done: {run.completed_items} completed, {run.failed_items} failed"
            )

            run = await orch.score_run(session, run.id)
            click.echo(f"Run {run.id} finalized (status: {run.status})")

            await session.commit()

        await engine.dispose()

    asyncio.run(_run())


@eval_group.command("run-matrix")
@click.option("--evaluation", required=True, help="Evaluation name or ID.")
@click.option("--targets", required=True, help="Comma-separated target IDs.")
@click.option("--name", default=None, help="Matrix run group name.")
@click.pass_context
def run_matrix(ctx: click.Context, evaluation: str, targets: str, name: str | None):
    """Execute a matrix of evaluation runs across multiple targets."""
    settings = ctx.obj["settings"]

    async def _run():
        engine = _get_eval_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        target_ids = [int(t.strip()) for t in targets.split(",")]
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            from ..execution.orchestrator import RunOrchestrator
            from ..services import run_service

            ev_id = await _resolve_eval(session, evaluation)

            rg, runs = await run_service.create_batch(
                session,
                evaluation_version_id=ev_id,
                target_config_ids=target_ids,
                execution_type="matrix",
                name=name,
                total_items=0,
            )
            click.echo(f"Matrix group {rg.id}: {len(runs)} runs created")

            orch = RunOrchestrator()
            for r in runs:
                r = await orch.execute_run(session, r.id)
                r = await orch.score_run(session, r.id)
                click.echo(f"  Run {r.id}: {r.status} ({r.completed_items}/{r.total_items})")

            await session.commit()

        await engine.dispose()

    asyncio.run(_run())


@eval_group.command("status")
@click.option("--run-id", type=int, default=None, help="Show specific run.")
@click.option("--active", is_flag=True, help="Show all non-terminal runs.")
@click.option("--recent", type=int, default=None, help="Show N most recent runs.")
@click.pass_context
def eval_status(ctx: click.Context, run_id: int | None, active: bool, recent: int | None):
    """Show run status."""
    settings = ctx.obj["settings"]

    async def _status():
        engine = _get_eval_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            from ..services import run_service

            if run_id:
                run = await run_service.get_run(session, run_id)
                if run is None:
                    click.echo(f"Run {run_id} not found.")
                    return
                _print_run_detail(run)
            elif active:
                for status in ("queued", "running", "scoring"):
                    runs = await run_service.list_runs(session, status=status)
                    for r in runs:
                        _print_run_row(r)
            else:
                limit = recent or 10
                runs = await run_service.list_runs(session, limit=limit)
                _print_run_table(runs)

        await engine.dispose()

    asyncio.run(_status())


@eval_group.command("list")
@click.option("--evaluations", is_flag=True, help="List evaluations.")
@click.option("--datasets", is_flag=True, help="List datasets.")
@click.option("--scorers", is_flag=True, help="List scorers.")
@click.option("--targets", is_flag=True, help="List targets.")
@click.option("--machines", is_flag=True, help="List machines.")
@click.pass_context
def eval_list(
    ctx: click.Context,
    evaluations: bool,
    datasets: bool,
    scorers: bool,
    targets: bool,
    machines: bool,
):
    """List evaluation entities."""
    settings = ctx.obj["settings"]

    if not any([evaluations, datasets, scorers, targets, machines]):
        click.echo(
            "Specify at least one: --evaluations, --datasets, --scorers, --targets, --machines"
        )
        return

    async def _list():
        engine = _get_eval_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            if evaluations:
                from ..services import eval_service

                items = await eval_service.list_evaluations(session)
                click.echo(f"\nEvaluations ({len(items)}):")
                for e in items:
                    click.echo(f"  [{e.id}] {e.name} ({e.execution_mode})")

            if datasets:
                from ..services import dataset_service

                items = await dataset_service.list_datasets(session)
                click.echo(f"\nDatasets ({len(items)}):")
                for d in items:
                    click.echo(f"  [{d.id}] {d.name} (source: {d.source or 'N/A'})")

            if scorers:
                from ..services import scorer_service

                items = await scorer_service.list_scorers(session)
                click.echo(f"\nScorers ({len(items)}):")
                for s in items:
                    click.echo(f"  [{s.id}] {s.name} ({s.scorer_type})")

            if targets:
                from ..services import target_service

                items = await target_service.list_targets(session)
                click.echo(f"\nTargets ({len(items)}):")
                for t in items:
                    click.echo(f"  [{t.id}] {t.name} ({t.provider}/{t.model_name})")

            if machines:
                from ..services import machine_service

                items = await machine_service.list_profiles(session)
                click.echo(f"\nMachines ({len(items)}):")
                for m in items:
                    click.echo(f"  [{m.id}] {m.hostname} ({m.hardware_class})")

        await engine.dispose()

    asyncio.run(_list())


@eval_group.command("compare")
@click.option("--runs", required=True, help="Comma-separated run IDs to compare.")
@click.option("--format", "fmt", type=click.Choice(["text", "json", "csv"]), default="text")
@click.pass_context
def eval_compare(ctx: click.Context, runs: str, fmt: str):
    """Compare evaluation runs."""
    settings = ctx.obj["settings"]

    async def _compare():
        engine = _get_eval_engine(settings)
        session_factory = create_session_factory(engine)
        run_ids = [int(r.strip()) for r in runs.split(",")]

        async with session_factory() as session:
            from ..services import comparison_service

            result = await comparison_service.compare_runs(session, run_ids)

            if fmt == "json":
                click.echo(json.dumps(result, indent=2, default=str))
            elif fmt == "csv":
                from ..services import report_service

                rows = result.get("metric_deltas", {})
                click.echo(report_service.export_csv([rows] if rows else []))
            else:
                deltas = result.get("metric_deltas", {})
                click.echo("Metric Deltas:")
                for name, vals in deltas.items():
                    click.echo(f"  {name}: {vals}")
                diffs = result.get("item_diffs", [])
                if diffs:
                    click.echo(f"\nItem disagreements: {len(diffs)}")

        await engine.dispose()

    asyncio.run(_compare())


@eval_group.command("export")
@click.option("--run", "run_id", type=int, required=True, help="Run ID to export.")
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "html"]), default="json")
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None)
@click.pass_context
def eval_export(ctx: click.Context, run_id: int, fmt: str, output_path: Path | None):
    """Export run results."""
    settings = ctx.obj["settings"]

    async def _export():
        engine = _get_eval_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            from ..services import report_service, run_service

            run = await run_service.get_run(session, run_id)
            if run is None:
                click.echo(f"Run {run_id} not found.")
                return

            items = await run_service.get_item_results(session, run_id, limit=10000)
            metrics = await run_service.get_metrics(session, run_id)

            data = {
                "run_id": run.id,
                "status": run.status,
                "total_items": run.total_items,
                "completed_items": run.completed_items,
                "failed_items": run.failed_items,
                "metrics": {m.metric_name: m.metric_value for m in metrics},
                "items": [
                    {
                        "index": i.item_index,
                        "output": i.raw_output,
                        "pass": i.overall_pass,
                        "latency_ms": i.latency_ms,
                        "error": i.error_message,
                    }
                    for i in items
                ],
            }

            if fmt == "json":
                content = report_service.export_json(data)
            elif fmt == "csv":
                content = report_service.export_csv(data["items"])
            else:
                content = report_service.export_html(data, title=f"Run {run_id}")

            if output_path:
                output_path.write_text(content, encoding="utf-8")
                click.echo(f"Exported run {run_id} to {output_path}")
            else:
                click.echo(content)

        await engine.dispose()

    asyncio.run(_export())


@eval_group.command("rescore")
@click.option("--run", "run_id", type=int, required=True, help="Run ID to rescore.")
@click.option(
    "--scorer-config",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to JSON scorer config file.",
)
@click.pass_context
def eval_rescore(ctx: click.Context, run_id: int, scorer_config: Path):
    """Rescore a run with new scorer configuration."""
    settings = ctx.obj["settings"]

    async def _rescore():
        engine = _get_eval_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        config = json.loads(scorer_config.read_text(encoding="utf-8"))

        async with session_factory() as session:
            from ..execution.orchestrator import RunOrchestrator
            from ..models.evaluation import EvaluationVersion
            from ..services import run_service

            run = await run_service.get_run(session, run_id)
            if run is None:
                click.echo(f"Run {run_id} not found.")
                return

            ev = await session.get(EvaluationVersion, run.evaluation_version_id)
            if ev:
                ev.scorer_config = json.dumps(config)
                await session.flush()

            orch = RunOrchestrator()
            run = await orch.score_run(session, run_id)
            await session.commit()
            click.echo(f"Run {run_id} rescored (status: {run.status})")

            metrics = await run_service.get_metrics(session, run_id)
            for m in metrics:
                click.echo(f"  {m.metric_name}: {m.metric_value:.4f}")

        await engine.dispose()

    asyncio.run(_rescore())


@eval_group.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8100, type=int, help="Bind port.")
def eval_serve(host: str, port: int):
    """Start the evaluation API server."""
    import uvicorn

    from ..api.app import create_app
    from ..config import EvalSettings

    settings = EvalSettings()
    app = create_app(settings)
    uvicorn.run(app, host=host, port=port)


# ── Helpers ──


async def _resolve_eval(session, name_or_id: str) -> int:
    """Resolve evaluation name or ID to the latest version ID."""
    from sqlalchemy import select

    from ..models.evaluation import EvaluationVersion
    from ..services import eval_service

    try:
        eval_id = int(name_or_id)
        # Check if this is a version ID directly
        ev = await session.get(EvaluationVersion, eval_id)
        if ev:
            return eval_id
    except ValueError:
        pass

    # Try as evaluation name
    evals = await eval_service.list_evaluations(session, name=name_or_id)
    if not evals:
        raise click.ClickException(f"Evaluation '{name_or_id}' not found")

    # Get latest version
    stmt = (
        select(EvaluationVersion)
        .where(EvaluationVersion.evaluation_id == evals[0].id)
        .order_by(EvaluationVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    ev = result.scalar_one_or_none()
    if ev is None:
        raise click.ClickException(f"Evaluation '{name_or_id}' has no versions")
    return ev.id


async def _resolve_target(session, name_or_id: str) -> int:
    """Resolve target name or ID."""
    from ..services import target_service

    try:
        target_id = int(name_or_id)
        t = await target_service.get_target(session, target_id)
        if t:
            return target_id
    except ValueError:
        pass

    targets = await target_service.list_targets(session, model_name=name_or_id)
    if not targets:
        raise click.ClickException(f"Target '{name_or_id}' not found")
    return targets[0].id


def _print_run_table(runs):
    click.echo(f"{'ID':>5} {'Status':<20} {'Items':>8} {'Completed':>10} {'Failed':>8}")
    click.echo("-" * 55)
    for r in runs:
        _print_run_row(r)


def _print_run_row(r):
    click.echo(
        f"{r.id:>5} {r.status:<20} {r.total_items:>8} {r.completed_items:>10} {r.failed_items:>8}"
    )


def _print_run_detail(r):
    click.echo(f"Run {r.id}")
    click.echo(f"  Status: {r.status}")
    click.echo(
        f"  Items: {r.total_items} total, {r.completed_items} completed, {r.failed_items} failed"
    )
    click.echo(f"  Trigger: {r.trigger_type}")
    if r.started_at:
        click.echo(f"  Started: {r.started_at}")
    if r.completed_at:
        click.echo(f"  Completed: {r.completed_at}")
    if r.error_message:
        click.echo(f"  Error: {r.error_message}")
