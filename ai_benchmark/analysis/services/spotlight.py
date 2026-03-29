"""New Model Spotlight: identifies recently-appeared models with benchmark context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import CrossReference, EventRecord
from ..models import AnalysisInsight
from ..types import SpotlightEntry, SpotlightReport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_spotlight(
    session: AsyncSession,
    *,
    window_days: int = 30,
    min_benchmarks: int = 1,
    organization: str | None = None,
) -> SpotlightReport:
    """New models in the window, ranked by benchmark debut strength."""
    from .benchmark_trends import extract_benchmark_score, list_benchmarks
    from .model_lifecycle import list_tracked_models

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # All tracked models, optionally filtered by org
    all_models = await list_tracked_models(session, organization=organization, limit=500)

    # Filter to new models (first_seen within window)
    new_models = [m for m in all_models if m.first_seen and m.first_seen >= cutoff_str]

    # Get all benchmark variants
    benchmarks = await list_benchmarks(session)
    benchmark_names = [b.benchmark_name for b in benchmarks]

    # Build leaderboard scores per benchmark: {benchmark: {model_slug: best_score}}
    leaderboard_scores: dict[str, dict[str, float]] = {}
    for bname in benchmark_names:
        stmt = (
            select(EventRecord)
            .where(EventRecord.benchmark_variant == bname)
            .where(EventRecord.raw_content.is_not(None))
        )
        result = await session.execute(stmt)
        events = list(result.scalars().all())

        scores: dict[str, float] = {}
        for event in events:
            score = extract_benchmark_score(event.raw_content or "", bname)
            if (
                score is not None
                and event.model_slug
                and (event.model_slug not in scores or score > scores[event.model_slug])
            ):
                scores[event.model_slug] = score
        leaderboard_scores[bname] = scores

    entries = []
    for model in new_models:
        slug = model.model_slug

        # Best scores per benchmark
        best_scores: dict[str, float] = {}
        debut_strength = 0
        for bname, scores in leaderboard_scores.items():
            if slug in scores:
                best_scores[bname] = scores[slug]
                # Check if top-3 in this benchmark
                sorted_scores = sorted(scores.values(), reverse=True)
                rank = sorted_scores.index(scores[slug]) + 1
                if rank <= 3:
                    debut_strength += 1

        benchmark_count = len(best_scores)
        if benchmark_count < min_benchmarks:
            continue

        # CrossReference "confirms" count
        xref_stmt = (
            select(func.count(CrossReference.id))
            .join(
                EventRecord,
                (CrossReference.record_a_id == EventRecord.id)
                | (CrossReference.record_b_id == EventRecord.id),
            )
            .where(EventRecord.model_slug == slug)
            .where(CrossReference.relationship_type == "confirms")
        )
        xref_result = await session.execute(xref_stmt)
        xref_count = xref_result.scalar() or 0

        # Insight flags
        insight_stmt = (
            select(AnalysisInsight.insight_type)
            .where(AnalysisInsight.related_model_slug == slug)
            .distinct()
        )
        insight_result = await session.execute(insight_stmt)
        insight_flags = [r[0] for r in insight_result.all()]

        entries.append(
            SpotlightEntry(
                model_slug=slug,
                organization=model.organization,
                first_seen=model.first_seen or "",
                status=model.status,
                benchmark_count=benchmark_count,
                best_scores=best_scores,
                debut_strength=debut_strength,
                xref_count=xref_count,
                insight_flags=insight_flags,
            )
        )

    # Sort by debut_strength descending, then benchmark_count
    entries.sort(key=lambda e: (-e.debut_strength, -e.benchmark_count))

    return SpotlightReport(
        window_days=window_days,
        cutoff_date=cutoff_str,
        total_new_models=len(entries),
        entries=entries,
    )
