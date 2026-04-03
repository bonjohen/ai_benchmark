"""CLI entry point for the AI benchmark pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

if TYPE_CHECKING:
    from datetime import datetime

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
        from .models import discovery, events, research, sources  # noqa: F401

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
        click.echo(
            f"  [{s.classification}] {s.source_name} ({len(s.pages)} pages, trust={s.trust_rating})"
        )


@cli.command()
@click.option("--source", default=None, help="Collect from a single source organization.")
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Backfill historical data to this date (YYYY-MM-DD).",
)
@click.pass_context
def collect(ctx: click.Context, source: str | None, since: click.DateTime | None) -> None:
    """Run collection for one or all sources immediately."""
    settings: PipelineSettings = ctx.obj["settings"]
    since_date = since.date() if since else None

    if since_date:
        click.echo(f"Backfill mode: collecting data since {since_date.isoformat()}")

    async def _collect() -> None:
        from .coordination.coordinator import CollectionCoordinator

        coordinator = CollectionCoordinator(settings)
        await coordinator.setup()
        try:
            organizations = [source] if source else None
            stats = await coordinator.collect_all(
                organizations=organizations,
                since_date=since_date,
            )
        finally:
            await coordinator.shutdown()

        click.echo("Collection complete.")
        click.echo(
            f"  Tasks: {stats['tasks_created']} created, "
            f"{stats['tasks_completed']} completed, "
            f"{stats['tasks_failed']} failed"
        )
        click.echo(f"  Items processed: {stats['items_processed']}")
        click.echo(f"  Events created: {stats['events_created']}")

    asyncio.run(_collect())


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show per-source health status."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _status() -> None:
        from .models.base import create_engine, create_session_factory
        from .reporting.query import count_events_by_org, count_research_by_source

        engine = create_engine(settings.database_url)
        from .models import events, research  # noqa: F401

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            counts = await count_events_by_org(session)
            research_counts = await count_research_by_source(session)

        # Map discovered_via values to org names for display
        research_org_map = {
            "arxiv": "arXiv / Cornell",
            "hf_papers": "Hugging Face Papers",
            "semantic_scholar": "Ai2",
        }

        sources = load_source_catalog()
        click.echo(f"{'Source':<30} {'Classification':<18} {'Events':>8} {'Papers':>8}")
        click.echo("-" * 68)
        for s in sources:
            event_count = counts.get(s.organization, 0)
            paper_count = 0
            for via, org_name in research_org_map.items():
                if s.organization == org_name:
                    paper_count = research_counts.get(via, 0)
            click.echo(
                f"{s.organization:<30} {s.classification:<18} {event_count:>8} {paper_count:>8}"
            )

        await engine.dispose()

    asyncio.run(_status())


@cli.command()
@click.option("--org", default=None, help="Filter by organization.")
@click.option("--type", "event_type", default=None, help="Filter by event type.")
@click.option("--model", default=None, help="Filter by model slug.")
@click.option("--limit", default=20, help="Number of results.")
@click.option("--format", "fmt", type=click.Choice(["text", "json", "csv"]), default="text")
@click.pass_context
def query(
    ctx: click.Context,
    org: str | None,
    event_type: str | None,
    model: str | None,
    limit: int,
    fmt: str,
) -> None:
    """Search events in the knowledge base."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _query() -> None:
        from .reporting.export import events_to_csv, events_to_json
        from .reporting.query import get_events

        engine = create_engine(settings.database_url)
        from .models import events as ev_models  # noqa: F401

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
                click.echo(
                    f"[{e.event_type}] {e.organization}: "
                    f"{e.title} ({e.published_date or 'no date'})"
                )

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
        from .reporting.export import events_to_csv, events_to_json
        from .reporting.query import get_events

        engine = create_engine(settings.database_url)
        from .models import events as ev_models  # noqa: F401

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            results = await get_events(session, limit=limit)

        content = events_to_json(results) if fmt == "json" else events_to_csv(results)

        if output_path:
            output_path.write_text(content, encoding="utf-8")
            click.echo(f"Exported {len(results)} events to {output_path}")
        else:
            click.echo(content)

        await engine.dispose()

    asyncio.run(_export())


@cli.command()
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None)
@click.option("--hours", default=24, help="Lookback window in hours.")
@click.option(
    "--date",
    "report_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Generate report for a specific date (YYYY-MM-DD). Overrides --hours.",
)
@click.pass_context
def report(
    ctx: click.Context,
    output_path: Path | None,
    hours: int,
    report_date: datetime | None,
) -> None:
    """Generate a daily intelligence report as JSON."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _report() -> None:
        from .reporting.report_formatter import format_json
        from .reporting.report_queries import gather_daily_report

        engine = create_engine(settings.database_url)
        from .models import events as ev_models  # noqa: F401

        ref_date = report_date.date() if report_date else None
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            data = await gather_daily_report(session, hours=hours, reference_date=ref_date)

        content = format_json(data)

        if output_path:
            output_path.write_text(content, encoding="utf-8")
            click.echo(f"Report written to {output_path}")
        else:
            click.echo(content)

        await engine.dispose()

    asyncio.run(_report())


@cli.command("report-range")
@click.option(
    "--since",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD, inclusive).",
)
@click.option(
    "--until",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="End date (YYYY-MM-DD, inclusive). Defaults to today.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory to write raw_articles_YYYYMMDD.json files.",
)
@click.pass_context
def report_range(
    ctx: click.Context,
    since: datetime,
    until: datetime | None,
    output_dir: Path,
) -> None:
    """Extract daily report JSON for every date in a range."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _range() -> None:
        from datetime import date, timedelta

        from .reporting.report_formatter import format_json
        from .reporting.report_queries import gather_daily_report

        engine = create_engine(settings.database_url)
        from .models import events as ev_models  # noqa: F401

        output_dir.mkdir(parents=True, exist_ok=True)

        start = since.date()
        end = until.date() if until else date.today()

        session_factory = create_session_factory(engine)
        total = 0
        with_articles = 0
        current = start
        async with session_factory() as session:
            while current <= end:
                data = await gather_daily_report(session, reference_date=current)
                content = format_json(data)
                fname = f"raw_articles_{current.strftime('%Y%m%d')}.json"
                (output_dir / fname).write_text(content, encoding="utf-8")
                total += 1
                if data.articles:
                    with_articles += 1
                current += timedelta(days=1)

        click.echo(
            f"Generated {total} reports ({with_articles} with articles,"
            f" {total - with_articles} empty)"
        )
        await engine.dispose()

    asyncio.run(_range())


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
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, _signal_handler)

        try:
            await stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            scheduler.shutdown()
            await scheduler.shutdown_coordinator()
            click.echo("Pipeline stopped.")

    asyncio.run(_run())


@cli.command("cleanup-slugs")
@click.pass_context
def cleanup_slugs(ctx: click.Context) -> None:
    """Clean up invalid model slugs and orphaned cross-references."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _cleanup() -> None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .processing.normalizer import cleanup_invalid_slugs

            result = await cleanup_invalid_slugs(session)
            await session.commit()
        await engine.dispose()

        click.echo("Slug cleanup complete:")
        click.echo(f"  Events cleaned: {result['slugs_cleaned']}")
        click.echo(f"  Cross-references removed: {result['xrefs_removed']}")

    asyncio.run(_cleanup())


@cli.command("cleanup-lmarena")
@click.pass_context
def cleanup_lmarena(ctx: click.Context) -> None:
    """Delete all bad LMArena event records, claims, and cross-references."""
    settings: PipelineSettings = ctx.obj["settings"]

    async def _cleanup() -> None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .processing.normalizer import cleanup_lmarena_data

            result = await cleanup_lmarena_data(session)
            await session.commit()
        await engine.dispose()

        click.echo("LMArena cleanup complete:")
        click.echo(f"  Events deleted: {result['events_deleted']}")
        click.echo(f"  Claims deleted: {result['claims_deleted']}")
        click.echo(f"  Cross-references deleted: {result['xrefs_deleted']}")

    asyncio.run(_cleanup())


if __name__ == "__main__":
    cli()
