"""CLI entry point for the AI benchmark pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
import structlog

from .config.settings import PipelineSettings, load_source_catalog
from .models.base import Base, create_engine

logger = structlog.get_logger()


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AI Benchmark Intelligence Pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = PipelineSettings()


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
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the pipeline (stub — implemented in Phase 7)."""
    click.echo("Pipeline run not yet implemented. See Phase 7 in the plan.")


if __name__ == "__main__":
    cli()
