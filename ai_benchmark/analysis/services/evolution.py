"""Benchmark Evolution: temporal trends, frontier progression, saturation analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..types import EvolutionSummary, FrontierEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_benchmark_evolution(
    session: AsyncSession,
    *,
    benchmark_name: str | None = None,
    window_days: int = 180,
) -> list[EvolutionSummary]:
    """Compute evolution summaries for one or all benchmarks."""
    from .benchmark_trends import (
        extract_benchmark_score,
        get_benchmark_leaderboard,
        get_benchmark_timeline,
        list_benchmarks,
    )

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    if benchmark_name:
        names = [benchmark_name]
    else:
        benchmarks = await list_benchmarks(session)
        names = [b.benchmark_name for b in benchmarks]

    summaries = []
    for name in names:
        summary = await _compute_evolution(
            session,
            name,
            window_days=window_days,
            cutoff_str=cutoff_str,
            get_benchmark_timeline=get_benchmark_timeline,
            get_benchmark_leaderboard=get_benchmark_leaderboard,
            extract_benchmark_score=extract_benchmark_score,
        )
        summaries.append(summary)

    return summaries


async def _compute_evolution(
    session,
    benchmark_name: str,
    *,
    window_days: int,
    cutoff_str: str,
    get_benchmark_timeline,
    get_benchmark_leaderboard,
    extract_benchmark_score,
) -> EvolutionSummary:
    """Compute evolution for a single benchmark."""
    # Get full timeline
    timeline = await get_benchmark_timeline(session, benchmark_name)

    # Filter to window
    in_window = [dp for dp in timeline if dp.date >= cutoff_str]

    if not in_window:
        return EvolutionSummary(
            benchmark_name=benchmark_name,
            window_days=window_days,
        )

    # Collect scores: only data points with extracted scores
    scored = [(dp, dp.score) for dp in in_window if dp.score is not None]
    if not scored:
        return EvolutionSummary(
            benchmark_name=benchmark_name,
            window_days=window_days,
            models_evaluated=len({dp.model_slug for dp in in_window}),
        )

    # Distinct models
    models_evaluated = len({dp.model_slug for dp, _ in scored})

    # Sort by date for temporal analysis
    scored.sort(key=lambda x: x[0].date)

    # Earliest and latest top scores
    earliest_top = scored[0][1]
    latest_top = scored[-1][1]

    # Overall best scores for leader computation
    best_by_model: dict[str, float] = {}
    for dp, score in scored:
        if dp.model_slug not in best_by_model or score > best_by_model[dp.model_slug]:
            best_by_model[dp.model_slug] = score

    ranked = sorted(best_by_model.items(), key=lambda x: -x[1])
    current_leader = ranked[0][0] if ranked else None
    current_top_score = ranked[0][1] if ranked else None

    gap_to_second = None
    if len(ranked) >= 2:
        gap_to_second = round(ranked[0][1] - ranked[1][1], 4)

    # Total improvement and rate
    total_improvement = round(latest_top - earliest_top, 4) if len(scored) > 1 else None
    months = max(window_days / 30.0, 1.0)
    improvement_rate = (
        round(total_improvement / months, 4) if total_improvement is not None else None
    )

    # Frontier progression: chronological sequence of new all-time highs
    frontier: list[FrontierEntry] = []
    running_max = float("-inf")
    for dp, score in scored:
        if score > running_max:
            running_max = score
            frontier.append(
                FrontierEntry(
                    date=dp.date,
                    model_slug=dp.model_slug,
                    score=score,
                )
            )

    last_record_date = frontier[-1].date if frontier else None

    # Saturation: percentage-based benchmarks have ceiling=100
    saturation_pct = _compute_saturation(current_top_score, benchmark_name)

    return EvolutionSummary(
        benchmark_name=benchmark_name,
        window_days=window_days,
        total_improvement=total_improvement,
        improvement_rate_per_month=improvement_rate,
        current_leader=current_leader,
        current_top_score=current_top_score,
        gap_to_second=gap_to_second,
        models_evaluated=models_evaluated,
        saturation_pct=saturation_pct,
        last_record_date=last_record_date,
        frontier=frontier,
    )


def _compute_saturation(top_score: float | None, benchmark_name: str) -> float | None:
    """Estimate saturation percentage based on score type heuristics."""
    if top_score is None:
        return None

    name_lower = benchmark_name.lower()

    # ELO-like benchmarks have no fixed ceiling
    if "elo" in name_lower or "arena" in name_lower:
        return None
    if 1000 <= top_score <= 2000:
        return None

    # Percentage-based: ceiling is 100
    if top_score <= 100:
        return round(top_score / 100.0 * 100, 2)

    # Other: estimate ceiling as max + 10%
    ceiling = top_score * 1.1
    return round(top_score / ceiling * 100, 2)
