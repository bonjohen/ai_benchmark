"""Digest service: orchestrates all analysis products into a periodic summary."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..models import AnalysisSnapshot
from ..types import DigestReport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def generate_digest(
    session: AsyncSession,
    *,
    window_days: int = 7,
    persist: bool = True,
) -> DigestReport:
    """Orchestrate all services into a single digest."""
    from .anomaly_detector import detect_anomalies
    from .benchmark_trends import list_benchmarks
    from .competitive_intel import get_activity_timeline
    from .model_lifecycle import list_tracked_models
    from .research_pulse import get_research_trends

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)

    # Model updates: only models with recent activity
    all_models = await list_tracked_models(session, limit=500)
    model_updates = [
        m
        for m in all_models
        if m.latest_activity and m.latest_activity >= cutoff.strftime("%Y-%m-%d")
    ]

    # Benchmark movements
    benchmarks = await list_benchmarks(session)
    benchmark_movements = []
    for b in benchmarks:
        if b.top_model and b.top_score is not None:
            from ..types import BenchmarkDataPoint

            benchmark_movements.append(
                BenchmarkDataPoint(
                    model_slug=b.top_model,
                    score=b.top_score,
                    date=b.latest_date or "",
                    source_name=b.benchmark_name,
                    benchmark_variant=b.benchmark_name,
                )
            )

    # Competitive overview
    competitive_overview = await get_activity_timeline(session, window_days=window_days)

    # Research highlights
    research_highlights = await get_research_trends(session, window_days=max(window_days, 30))

    # Anomalies as headline insights
    anomalies = await detect_anomalies(session, window_days=window_days)
    headline_insights = [
        {
            "type": a.insight_type,
            "severity": a.severity,
            "title": a.title,
            "description": a.description,
        }
        for a in anomalies
    ]

    report = DigestReport(
        period_start=cutoff.strftime("%Y-%m-%d"),
        period_end=now.strftime("%Y-%m-%d"),
        headline_insights=headline_insights,
        model_updates=model_updates,
        benchmark_movements=benchmark_movements,
        competitive_overview=competitive_overview,
        research_highlights=research_highlights,
        stats={
            "total_models": len(all_models),
            "active_models": len(model_updates),
            "total_benchmarks": len(benchmarks),
            "anomalies_detected": len(anomalies),
        },
    )

    if persist:
        iso_week = now.isocalendar()
        snapshot = AnalysisSnapshot(
            analysis_type="digest",
            scope_key=f"weekly-{iso_week[0]}-W{iso_week[1]:02d}",
            window_start=cutoff,
            window_end=now,
            result_json=json.dumps(dataclasses.asdict(report), default=str),
            event_count=sum(m.event_count for m in model_updates),
            version=1,
        )
        session.add(snapshot)
        await session.flush()

    return report
