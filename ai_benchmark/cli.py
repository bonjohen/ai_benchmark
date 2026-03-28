"""CLI entry point for the AI benchmark pipeline."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

import click
import structlog

from .config.settings import PipelineSettings, load_source_catalog
from .main import configure_logging
from .models.base import Base, create_engine, create_session_factory

logger = structlog.get_logger()


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AI Benchmark Intelligence Pipeline."""
    ctx.ensure_object(dict)
    settings = PipelineSettings()
    ctx.obj["settings"] = settings
    configure_logging(settings.log_level, settings.log_format)


@cli.command()
@click.pass_context
def init_db(ctx: click.Context) -> None:
    """Initialize the database schema."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _init() -> None:
        engine = create_engine(settings.database_url)
        # Import all models so they register with Base.metadata
        from .models import events, research, sources  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        click.echo(f"Database initialized: {settings.database_url}")

    asyncio.run(_init())


@cli.command()
@click.option(
    "--catalog",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to sources.toml catalog file.",
)
def check_config(catalog: Path | None) -> None:
    """Validate the source catalog and pipeline settings."""
    settings = PipelineSettings()
    click.echo(f"Settings OK: database_url={settings.database_url}")

    sources = load_source_catalog(catalog)
    total_pages = sum(len(s.pages) for s in sources)
    click.echo(f"Source catalog OK: {len(sources)} sources, {total_pages} pages")

    for s in sources:
        click.echo(f"  [{s.classification}] {s.source_name} ({len(s.pages)} pages, trust={s.trust_rating})")


@cli.command()
@click.option("--source", default=None, help="Collect from a single source organization.")
@click.pass_context
def collect(ctx: click.Context, source: str | None) -> None:
    """Run collection for one or all sources immediately."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _collect() -> None:
        from .scheduling.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(settings)
        await scheduler.setup()

        if source:
            click.echo(f"Collecting from: {source}")
            await scheduler.collect_source(source)
        else:
            sources = load_source_catalog()
            for s in sources:
                click.echo(f"Collecting from: {s.organization}")
                await scheduler.collect_source(s.organization)

        click.echo("Collection complete.")

    asyncio.run(_collect())


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show per-source health status."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _status() -> None:
        from .models.base import create_engine, create_session_factory
        from .reporting.query import count_events_by_org

        engine = create_engine(settings.database_url)
        from .models import events, research, sources as src_models  # noqa: F401

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            counts = await count_events_by_org(session)

        sources = load_source_catalog()
        click.echo(f"{'Source':<30} {'Classification':<18} {'Events':>8}")
        click.echo("-" * 60)
        for s in sources:
            count = counts.get(s.organization, 0)
            click.echo(f"{s.organization:<30} {s.classification:<18} {count:>8}")

        await engine.dispose()

    asyncio.run(_status())


@cli.command()
@click.option("--org", default=None, help="Filter by organization.")
@click.option("--type", "event_type", default=None, help="Filter by event type.")
@click.option("--model", default=None, help="Filter by model slug.")
@click.option("--limit", default=20, help="Number of results.")
@click.option("--format", "fmt", type=click.Choice(["text", "json", "csv"]), default="text")
@click.pass_context
def query(ctx: click.Context, org: str | None, event_type: str | None,
          model: str | None, limit: int, fmt: str) -> None:
    """Search events in the knowledge base."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _query() -> None:
        from .reporting.query import get_events
        from .reporting.export import events_to_json, events_to_csv

        engine = create_engine(settings.database_url)
        from .models import events as ev_models, research, sources as src_models  # noqa: F401

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            results = await get_events(
                session,
                organization=org,
                event_type=event_type,
                model_slug=model,
                limit=limit,
            )

        if fmt == "json":
            click.echo(events_to_json(results))
        elif fmt == "csv":
            click.echo(events_to_csv(results))
        else:
            for e in results:
                click.echo(f"[{e.event_type}] {e.organization}: {e.title} ({e.published_date or 'no date'})")

        await engine.dispose()

    asyncio.run(_query())


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None)
@click.option("--limit", default=1000, help="Max events to export.")
@click.pass_context
def export(ctx: click.Context, fmt: str, output_path: Path | None, limit: int) -> None:
    """Export events to JSON or CSV."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _export() -> None:
        from .reporting.query import get_events
        from .reporting.export import events_to_json, events_to_csv

        engine = create_engine(settings.database_url)
        from .models import events as ev_models, research, sources as src_models  # noqa: F401

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            results = await get_events(session, limit=limit)

        if fmt == "json":
            content = events_to_json(results)
        else:
            content = events_to_csv(results)

        if output_path:
            output_path.write_text(content, encoding="utf-8")
            click.echo(f"Exported {len(results)} events to {output_path}")
        else:
            click.echo(content)

        await engine.dispose()

    asyncio.run(_export())


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Start the pipeline in daemon mode with scheduled collection."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _run() -> None:
        from .scheduling.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(settings)
        await scheduler.setup()
        count = scheduler.load_all_schedules()
        click.echo(f"Loaded {count} schedules. Starting daemon...")
        scheduler.start()

        # Graceful shutdown on SIGINT/SIGTERM
        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            click.echo("\nShutting down...")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        try:
            await stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            scheduler.shutdown()
            click.echo("Pipeline stopped.")

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
