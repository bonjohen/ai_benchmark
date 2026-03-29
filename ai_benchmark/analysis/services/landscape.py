"""Competitive landscape: org-level synthesis with benchmark context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import EventRecord
from ..types import LandscapeReport, OrgLandscapeEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_landscape(
    session: AsyncSession,
    *,
    window_days: int = 30,
    organization: str | None = None,
) -> LandscapeReport:
    """Competitive landscape with benchmark context per organization."""
    from .benchmark_trends import extract_benchmark_score
    from .competitive_intel import get_activity_timeline
    from .model_lifecycle import list_tracked_models

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    prior_cutoff = cutoff - timedelta(days=window_days)

    timeline = await get_activity_timeline(session, window_days=window_days)

    # Filter to requested org if specified
    org_activities = timeline.org_activities
    if organization:
        org_activities = [oa for oa in org_activities if oa.organization == organization]

    entries = []
    for oa in org_activities:
        org_name = oa.organization

        # Get models for this org
        models = await list_tracked_models(session, organization=org_name, limit=500)
        new_models = [m for m in models if m.first_seen and m.first_seen >= cutoff_str]

        # Benchmark data for org models
        bench_stmt = (
            select(EventRecord)
            .where(EventRecord.organization == org_name)
            .where(EventRecord.benchmark_variant.is_not(None))
            .where(EventRecord.raw_content.is_not(None))
        )
        bench_result = await session.execute(bench_stmt)
        bench_events = list(bench_result.scalars().all())

        # Collect scores per benchmark per model
        benchmarks_seen: set[str] = set()
        best_score: float | None = None
        best_model: str | None = None
        best_benchmark: str | None = None
        all_scores: list[float] = []

        for event in bench_events:
            score = extract_benchmark_score(event.raw_content or "", event.benchmark_variant)
            if score is not None:
                benchmarks_seen.add(event.benchmark_variant)
                all_scores.append(score)
                if best_score is None or score > best_score:
                    best_score = score
                    best_model = event.model_slug
                    best_benchmark = event.benchmark_variant

        # Pricing events
        pricing_stmt = (
            select(func.count(EventRecord.id))
            .where(EventRecord.organization == org_name)
            .where(EventRecord.event_type == "pricing_change")
            .where(EventRecord.observed_at >= cutoff)
        )
        pricing_result = await session.execute(pricing_stmt)
        pricing_events = pricing_result.scalar() or 0

        # Price drop check from anomaly insights
        from ..models import AnalysisInsight

        drop_stmt = (
            select(func.count(AnalysisInsight.id))
            .where(AnalysisInsight.insight_type == "price_drop")
            .where(AnalysisInsight.related_org == org_name)
        )
        drop_result = await session.execute(drop_stmt)
        has_price_drop = (drop_result.scalar() or 0) > 0

        # Cluster participation
        cluster_count = sum(1 for c in timeline.clusters if org_name in c.organizations)

        # Trend: compare event count to prior window
        prior_stmt = (
            select(func.count(EventRecord.id))
            .where(EventRecord.organization == org_name)
            .where(EventRecord.observed_at >= prior_cutoff)
            .where(EventRecord.observed_at < cutoff)
        )
        prior_result = await session.execute(prior_stmt)
        prior_count = prior_result.scalar() or 0
        current_count = oa.total_events

        if current_count > prior_count * 1.2:
            trend = "up"
        elif current_count < prior_count * 0.8:
            trend = "down"
        else:
            trend = "stable"

        entries.append(
            OrgLandscapeEntry(
                organization=org_name,
                total_models=len(models),
                new_models=len(new_models),
                active_model_slugs=oa.active_models,
                benchmark_breadth=len(benchmarks_seen),
                avg_percentile=None,  # requires full normalization, computed if needed
                best_result_model=best_model,
                best_result_benchmark=best_benchmark,
                best_result_score=best_score,
                pricing_events=pricing_events,
                has_price_drop=has_price_drop,
                cluster_count=cluster_count,
                trend=trend,
            )
        )

    # Sort by total events descending
    entries.sort(key=lambda e: -e.total_models)

    return LandscapeReport(
        window_days=window_days,
        window_start=cutoff_str,
        window_end=now.strftime("%Y-%m-%d"),
        entries=entries,
    )
