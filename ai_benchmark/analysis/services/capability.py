"""Cross-benchmark capability profiles with percentile normalization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from ...models.events import EventRecord
from ..types import BenchmarkPercentile, CapabilityProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _extract_model_scores(
    session: AsyncSession,
    model_slug: str,
    benchmark_names: list[str],
) -> dict[str, float]:
    """Extract best score per benchmark for a model from raw event content."""
    from .benchmark_trends import extract_benchmark_score

    model_benchmarks: dict[str, float] = {}
    for bname in benchmark_names:
        stmt = (
            select(EventRecord)
            .where(EventRecord.model_slug == model_slug)
            .where(EventRecord.benchmark_variant == bname)
            .where(EventRecord.raw_content.is_not(None))
        )
        result = await session.execute(stmt)
        for event in result.scalars().all():
            score = extract_benchmark_score(event.raw_content or "", bname)
            if score is not None and (
                bname not in model_benchmarks or score > model_benchmarks[bname]
            ):
                model_benchmarks[bname] = score
    return model_benchmarks


async def _get_all_benchmark_scores(
    session: AsyncSession,
    benchmark_name: str,
) -> list[float]:
    """Get all extracted scores for a benchmark across all models."""
    from .benchmark_trends import extract_benchmark_score

    stmt = (
        select(EventRecord)
        .where(EventRecord.benchmark_variant == benchmark_name)
        .where(EventRecord.raw_content.is_not(None))
    )
    result = await session.execute(stmt)
    # Best score per model
    model_scores: dict[str, float] = {}
    for event in result.scalars().all():
        score = extract_benchmark_score(event.raw_content or "", benchmark_name)
        if (
            score is not None
            and event.model_slug
            and (event.model_slug not in model_scores or score > model_scores[event.model_slug])
        ):
            model_scores[event.model_slug] = score
    return list(model_scores.values())


async def get_capability_profile(
    session: AsyncSession,
    model_slug: str,
) -> CapabilityProfile | None:
    """Build a normalized capability profile for one model."""
    from .benchmark_trends import list_benchmarks
    from .model_lifecycle import build_model_profile

    profile = await build_model_profile(session, model_slug)
    if profile is None:
        return None

    # Get all known benchmarks and extract scores for this model
    benchmarks = await list_benchmarks(session)
    benchmark_names = [b.benchmark_name for b in benchmarks]
    model_benchmarks = await _extract_model_scores(session, model_slug, benchmark_names)

    if not model_benchmarks:
        return CapabilityProfile(
            model_slug=model_slug,
            organization=profile.organization,
            benchmark_count=0,
            percentiles=[],
            composite_score=0.0,
        )

    percentiles = []
    for bvariant, model_score in model_benchmarks.items():
        all_scores = await _get_all_benchmark_scores(session, bvariant)

        if not all_scores:
            continue

        # Percentile: fraction of scores below this model's score
        below = sum(1 for s in all_scores if s < model_score)
        total = len(all_scores)
        pct_rank = (below / max(total - 1, 1)) * 100.0 if total > 1 else 100.0

        percentiles.append(
            BenchmarkPercentile(
                benchmark_variant=bvariant,
                raw_score=model_score,
                percentile_rank=round(pct_rank, 2),
                models_in_benchmark=total,
            )
        )

    composite = (
        sum(p.percentile_rank for p in percentiles) / len(percentiles) if percentiles else 0.0
    )

    return CapabilityProfile(
        model_slug=model_slug,
        organization=profile.organization,
        benchmark_count=len(percentiles),
        percentiles=percentiles,
        composite_score=round(composite, 2),
    )


async def compare_capabilities(
    session: AsyncSession,
    model_slugs: list[str],
) -> list[CapabilityProfile]:
    """Build capability profiles for multiple models."""
    profiles = []
    for slug in model_slugs:
        profile = await get_capability_profile(session, slug)
        if profile is not None:
            profiles.append(profile)
    return profiles
