"""CLI commands for the analysis pipeline."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import click

from ..models.base import Base, create_engine, create_session_factory

if TYPE_CHECKING:
    from ..config.settings import PipelineSettings


def _get_analysis_engine(settings: PipelineSettings):
    """Create engine with all models registered."""
    engine = create_engine(settings.database_url)
    from ..models import discovery, events, research, sources  # noqa: F401
    from . import models as analysis_models  # noqa: F401

    return engine


@click.group("analyze")
def analyze_group() -> None:
    """Intelligence analysis of collected AI industry data."""


@analyze_group.command("models")
@click.option("--org", default=None, help="Filter by organization.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.option("--limit", default=100, help="Maximum number of models.")
@click.pass_context
def analyze_models(ctx: click.Context, org: str | None, output_format: str, limit: int) -> None:
    """List tracked AI models with event summaries."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.model_lifecycle import list_tracked_models

            models = await list_tracked_models(session, organization=org, limit=limit)

            if not models:
                click.echo("No tracked models found.")
                return

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(models))
            elif output_format == "markdown":
                from .formatters.markdown import model_list_to_markdown

                click.echo(model_list_to_markdown(models))
            elif output_format == "csv":
                from .formatters.csv_export import models_to_csv

                click.echo(models_to_csv(models))
            else:
                for m in models:
                    status_tag = f"[{m.status}]" if m.status != "active" else ""
                    click.echo(
                        f"  {m.model_slug:<30} {m.organization:<15} "
                        f"{m.event_count:>3} events  {status_tag}"
                    )

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("model")
@click.argument("slug")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_model(ctx: click.Context, slug: str, output_format: str) -> None:
    """Show detailed profile for a specific model."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.model_lifecycle import build_model_profile

            profile = await build_model_profile(session, slug)

            if profile is None:
                click.echo(f"Model '{slug}' not found.")
                return

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(profile))
            elif output_format == "markdown":
                from .formatters.markdown import model_profile_to_markdown

                click.echo(model_profile_to_markdown(profile))
            else:
                click.echo(f"Model: {profile.model_slug}")
                click.echo(f"Organization: {profile.organization}")
                click.echo(f"Status: {profile.status}")
                click.echo(f"First seen: {profile.first_seen or '—'}")
                click.echo(f"Latest: {profile.latest_activity or '—'}")

                if profile.claim_summary:
                    click.echo("\nClaims:")
                    for status, count in sorted(profile.claim_summary.items()):
                        click.echo(f"  {status}: {count}")

                if profile.milestones:
                    click.echo("\nTimeline:")
                    for m in profile.milestones:
                        click.echo(f"  {m.date}  {m.event_type:<20} {m.title}")

                if profile.benchmark_scores:
                    click.echo("\nBenchmarks:")
                    for b in profile.benchmark_scores:
                        score_str = f"{b.score}" if b.score is not None else "—"
                        click.echo(f"  {b.benchmark_variant}: {score_str} ({b.date})")

                if profile.related_models:
                    click.echo(f"\nRelated: {', '.join(profile.related_models)}")

        await engine.dispose()

    asyncio.run(_run())
