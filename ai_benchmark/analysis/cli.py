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


@analyze_group.command("benchmarks")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_benchmarks(ctx: click.Context, output_format: str) -> None:
    """List all tracked benchmarks."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.benchmark_trends import list_benchmarks

            benchmarks = await list_benchmarks(session)

            if not benchmarks:
                click.echo("No benchmarks found.")
                return

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(benchmarks))
            else:
                for b in benchmarks:
                    top = f"top: {b.top_model} ({b.top_score})" if b.top_model else ""
                    click.echo(f"  {b.benchmark_name:<30} {b.entry_count:>3} entries  {top}")

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("benchmark")
@click.argument("name")
@click.option("--model", "model_slug", default=None, help="Filter by model slug.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_benchmark(
    ctx: click.Context, name: str, model_slug: str | None, output_format: str
) -> None:
    """Show leaderboard for a specific benchmark."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.benchmark_trends import get_benchmark_leaderboard

            leaderboard = await get_benchmark_leaderboard(session, name)

            if not leaderboard.entries:
                click.echo(f"No entries found for benchmark '{name}'.")
                return

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(leaderboard))
            elif output_format == "markdown":
                from .formatters.markdown import leaderboard_to_markdown

                click.echo(leaderboard_to_markdown(leaderboard))
            elif output_format == "csv":
                from .formatters.csv_export import leaderboard_to_csv

                click.echo(leaderboard_to_csv(leaderboard))
            else:
                for i, entry in enumerate(leaderboard.entries, 1):
                    score_str = f"{entry.score}" if entry.score is not None else "—"
                    click.echo(
                        f"  {i:>3}. {entry.model_slug:<25} {score_str:>10} "
                        f"({entry.date}, {entry.source_name})"
                    )

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("competitive")
@click.option("--days", default=30, help="Lookback window in days.")
@click.option("--org", "organizations", multiple=True, help="Filter by organization(s).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_competitive(
    ctx: click.Context, days: int, organizations: tuple[str, ...], output_format: str
) -> None:
    """Show competitive activity timeline."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.competitive_intel import get_activity_timeline

            org_list = list(organizations) if organizations else None
            timeline = await get_activity_timeline(
                session, window_days=days, organizations=org_list
            )

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(timeline))
            elif output_format == "markdown":
                from .formatters.markdown import activity_timeline_to_markdown

                click.echo(activity_timeline_to_markdown(timeline))
            else:
                click.echo(f"Activity: {timeline.window_start} to {timeline.window_end}")
                if timeline.org_activities:
                    click.echo("\nOrganizations:")
                    for org in timeline.org_activities:
                        models_str = ", ".join(org.active_models[:5])
                        click.echo(
                            f"  {org.organization:<20} {org.total_events:>3} events  "
                            f"models: {models_str}"
                        )
                if timeline.clusters:
                    click.echo("\nCompetitive Clusters:")
                    for cluster in timeline.clusters:
                        orgs = ", ".join(cluster.organizations)
                        click.echo(
                            f"  {cluster.event_type}: {orgs} "
                            f"({cluster.start_date} to {cluster.end_date}, "
                            f"{cluster.event_count} events)"
                        )

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("research")
@click.option("--days", default=90, help="Lookback window in days.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_research(ctx: click.Context, days: int, output_format: str) -> None:
    """Show research pulse: trends, citations, paper-to-product links."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.research_pulse import get_research_trends

            trends = await get_research_trends(session, window_days=days)

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(trends))
            elif output_format == "markdown":
                from .formatters.markdown import research_trends_to_markdown

                click.echo(research_trends_to_markdown(trends))
            else:
                click.echo(f"Research Pulse ({trends.window_days} days)")
                click.echo(
                    f"  Papers: {trends.total_papers} total "
                    f"({trends.promoted_count} promoted, "
                    f"{trends.rejected_count} rejected, "
                    f"{trends.pending_count} pending)"
                )
                if trends.citation_leaders:
                    click.echo("\nCitation Leaders:")
                    for p in trends.citation_leaders[:10]:
                        click.echo(f"  {p.title[:60]:<60} {p.citation_count:>6} citations")
                if trends.topic_counts:
                    click.echo("\nTrending Topics:")
                    sorted_topics = sorted(trends.topic_counts.items(), key=lambda x: -x[1])
                    for topic, count in sorted_topics[:15]:
                        click.echo(f"  {topic}: {count}")

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("anomalies")
@click.option("--days", default=7, help="Lookback window in days.")
@click.option(
    "--severity",
    type=click.Choice(["info", "notable", "critical"]),
    default=None,
    help="Filter by severity.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_anomalies(
    ctx: click.Context, days: int, severity: str | None, output_format: str
) -> None:
    """Detect anomalies and show insights."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.anomaly_detector import detect_anomalies, get_recent_insights

            # Run detection
            new_insights = await detect_anomalies(session, window_days=days)
            await session.commit()

            # Get all recent insights (including previously detected)
            insights = await get_recent_insights(session, limit=50, severity=severity)

            if not insights:
                click.echo("No anomalies detected.")
                return

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json([_insight_to_dict(i) for i in insights]))
            elif output_format == "markdown":
                from .formatters.markdown import insights_to_markdown

                click.echo(insights_to_markdown(insights))
            elif output_format == "csv":
                from .formatters.csv_export import insights_to_csv

                click.echo(insights_to_csv(insights))
            else:
                if new_insights:
                    click.echo(f"Detected {len(new_insights)} new insight(s).\n")
                severity_icons = {
                    "critical": "!!!",
                    "notable": "!!",
                    "info": "i",
                }
                for insight in insights:
                    icon = severity_icons.get(insight.severity, "")
                    click.echo(f"  [{icon}] {insight.title}")
                    click.echo(f"       {insight.description}")

        await engine.dispose()

    asyncio.run(_run())


def _insight_to_dict(insight) -> dict:
    """Convert an AnalysisInsight ORM object to a plain dict."""
    return {
        "id": insight.id,
        "insight_type": insight.insight_type,
        "severity": insight.severity,
        "title": insight.title,
        "description": insight.description,
        "related_model_slug": insight.related_model_slug,
        "related_org": insight.related_org,
        "detected_at": str(insight.detected_at) if insight.detected_at else None,
    }


@analyze_group.command("digest")
@click.option("--days", default=7, help="Lookback window in days.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.option("--output", "output_file", default=None, help="Write output to file.")
@click.pass_context
def analyze_digest(
    ctx: click.Context, days: int, output_format: str, output_file: str | None
) -> None:
    """Generate a full periodic intelligence digest."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.digest import generate_digest

            report = await generate_digest(session, window_days=days, persist=True)
            await session.commit()

            if output_format == "json":
                from .formatters.json_export import to_json

                content = to_json(report)
            elif output_format == "markdown":
                from .formatters.markdown import digest_to_markdown

                content = digest_to_markdown(report)
            else:
                content = _digest_to_text(report)

            if output_file:
                from pathlib import Path

                Path(output_file).write_text(content, encoding="utf-8")
                click.echo(f"Digest written to {output_file}")
            else:
                click.echo(content)

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("run-all")
@click.option("--days", default=7, help="Lookback window in days.")
@click.pass_context
def analyze_run_all(ctx: click.Context, days: int) -> None:
    """Run all analysis services and persist results."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.anomaly_detector import detect_anomalies
            from .services.benchmark_trends import list_benchmarks
            from .services.competitive_intel import get_activity_timeline
            from .services.digest import generate_digest
            from .services.model_lifecycle import list_tracked_models
            from .services.research_pulse import get_research_trends

            click.echo("Running all analysis services...")

            models = await list_tracked_models(session)
            click.echo(f"  Models: {len(models)} tracked")

            benchmarks = await list_benchmarks(session)
            click.echo(f"  Benchmarks: {len(benchmarks)} tracked")

            timeline = await get_activity_timeline(session, window_days=days)
            click.echo(f"  Activity: {len(timeline.org_activities)} orgs active")

            trends = await get_research_trends(session, window_days=max(days, 30))
            click.echo(f"  Research: {trends.total_papers} papers")

            anomalies = await detect_anomalies(session, window_days=days)
            click.echo(f"  Anomalies: {len(anomalies)} detected")

            report = await generate_digest(session, window_days=days, persist=True)
            await session.commit()
            click.echo(f"\nDigest generated: {report.period_start} to {report.period_end}")

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("spotlight")
@click.option("--days", default=30, help="Lookback window in days.")
@click.option("--min-benchmarks", default=1, help="Minimum benchmark count.")
@click.option("--org", default=None, help="Filter by organization.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_spotlight(
    ctx: click.Context, days: int, min_benchmarks: int, org: str | None, output_format: str
) -> None:
    """Show new models ranked by benchmark performance."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.spotlight import get_spotlight

            report = await get_spotlight(
                session, window_days=days, min_benchmarks=min_benchmarks, organization=org
            )

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(report))
            elif output_format == "markdown":
                from .formatters.markdown import spotlight_to_markdown

                click.echo(spotlight_to_markdown(report))
            elif output_format == "csv":
                from .formatters.csv_export import spotlight_to_csv

                click.echo(spotlight_to_csv(report))
            else:
                from .formatters.markdown import spotlight_to_markdown

                click.echo(spotlight_to_markdown(report))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("evolution")
@click.option("--benchmark", default=None, help="Specific benchmark name.")
@click.option("--days", default=180, help="Lookback window in days.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_evolution(
    ctx: click.Context, benchmark: str | None, days: int, output_format: str
) -> None:
    """Show benchmark evolution and frontier progression."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.evolution import get_benchmark_evolution

            summaries = await get_benchmark_evolution(
                session, benchmark_name=benchmark, window_days=days
            )

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(summaries))
            elif output_format == "markdown":
                from .formatters.markdown import evolution_to_markdown

                click.echo(evolution_to_markdown(summaries))
            elif output_format == "csv":
                from .formatters.csv_export import evolution_to_csv

                click.echo(evolution_to_csv(summaries))
            else:
                from .formatters.markdown import evolution_to_markdown

                click.echo(evolution_to_markdown(summaries))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("capability")
@click.argument("slug")
@click.option("--compare", default=None, help="Comma-separated slugs to compare.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_capability(
    ctx: click.Context, slug: str, compare: str | None, output_format: str
) -> None:
    """Show cross-benchmark capability profile for a model."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            if compare:
                from .services.capability import compare_capabilities

                slugs = [slug] + [s.strip() for s in compare.split(",")]
                profiles = await compare_capabilities(session, slugs)
                if output_format == "json":
                    from .formatters.json_export import to_json

                    click.echo(to_json(profiles))
                else:
                    from .formatters.markdown import capability_to_markdown

                    for p in profiles:
                        click.echo(capability_to_markdown(p))
            else:
                from .services.capability import get_capability_profile

                profile = await get_capability_profile(session, slug)
                if profile is None:
                    click.echo(f"Model '{slug}' not found.")
                    return
                if output_format == "json":
                    from .formatters.json_export import to_json

                    click.echo(to_json(profile))
                else:
                    from .formatters.markdown import capability_to_markdown

                    click.echo(capability_to_markdown(profile))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("landscape")
@click.option("--days", default=30, help="Lookback window in days.")
@click.option("--org", default=None, help="Filter by organization.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_landscape(ctx: click.Context, days: int, org: str | None, output_format: str) -> None:
    """Show competitive landscape with benchmark context."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.landscape import get_landscape

            report = await get_landscape(session, window_days=days, organization=org)

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(report))
            else:
                from .formatters.markdown import landscape_to_markdown

                click.echo(landscape_to_markdown(report))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("verification")
@click.option("--org", default=None, help="Filter by organization.")
@click.option("--model", "model_slug", default=None, help="Filter by model slug.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_verification(
    ctx: click.Context, org: str | None, model_slug: str | None, output_format: str
) -> None:
    """Show claim verification dashboard."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.verification import get_verification_report

            report = await get_verification_report(session, organization=org, model_slug=model_slug)

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(report))
            elif output_format == "markdown":
                from .formatters.markdown import verification_to_markdown

                click.echo(verification_to_markdown(report))
            elif output_format == "csv":
                from .formatters.csv_export import verification_to_csv

                click.echo(verification_to_csv(report))
            else:
                from .formatters.markdown import verification_to_markdown

                click.echo(verification_to_markdown(report))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("correlations")
@click.option("--min-overlap", default=5, help="Minimum model overlap for correlation.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown", "csv"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_correlations(ctx: click.Context, min_overlap: int, output_format: str) -> None:
    """Show benchmark correlation matrix."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.correlation import get_correlation_matrix

            matrix = await get_correlation_matrix(session, min_overlap=min_overlap)

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(matrix))
            elif output_format == "markdown":
                from .formatters.markdown import correlation_to_markdown

                click.echo(correlation_to_markdown(matrix))
            elif output_format == "csv":
                from .formatters.csv_export import correlation_to_csv

                click.echo(correlation_to_csv(matrix))
            else:
                from .formatters.markdown import correlation_to_markdown

                click.echo(correlation_to_markdown(matrix))

        await engine.dispose()

    asyncio.run(_run())


@analyze_group.command("research-pipeline")
@click.option("--days", default=90, help="Lookback window in days.")
@click.option("--min-citations", default=0, help="Minimum citation count.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def analyze_research_pipeline(
    ctx: click.Context, days: int, min_citations: int, output_format: str
) -> None:
    """Show research-to-product pipeline: citation velocity, topic trends, predictive signals."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_analysis_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .services.research_pipeline import get_research_pipeline

            report = await get_research_pipeline(
                session, window_days=days, min_citations=min_citations
            )

            if output_format == "json":
                from .formatters.json_export import to_json

                click.echo(to_json(report))
            elif output_format == "markdown":
                from .formatters.markdown import research_pipeline_to_markdown

                click.echo(research_pipeline_to_markdown(report))
            else:
                from .formatters.markdown import research_pipeline_to_markdown

                click.echo(research_pipeline_to_markdown(report))

        await engine.dispose()

    asyncio.run(_run())


def _digest_to_text(report) -> str:
    """Simple text rendering of a DigestReport."""
    lines = [
        f"Intelligence Digest: {report.period_start} to {report.period_end}",
        "",
    ]
    if report.stats:
        for key, value in report.stats.items():
            lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        lines.append("")

    if report.headline_insights:
        lines.append("Headline Insights:")
        for insight in report.headline_insights:
            lines.append(f"  [{insight.get('severity', '')}] {insight.get('title', '')}")
        lines.append("")

    if report.model_updates:
        lines.append("Model Updates:")
        for m in report.model_updates:
            lines.append(f"  {m.model_slug} ({m.organization}) — {m.event_count} events")
        lines.append("")

    if report.benchmark_movements:
        lines.append("Benchmark Movements:")
        for b in report.benchmark_movements:
            score_str = f"{b.score}" if b.score is not None else "—"
            lines.append(f"  {b.benchmark_variant}: {b.model_slug} = {score_str}")
        lines.append("")

    return "\n".join(lines)
