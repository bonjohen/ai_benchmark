"""FastAPI router for the analysis pipeline."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _get_session_dep():
    """Import the eval app's get_session dependency."""
    from ..eval.api.app import get_session

    return get_session


_session = Depends(_get_session_dep())


def _to_dict(obj):
    """Convert a dataclass or list of dataclasses to a JSON-serializable dict."""
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


@router.get("/models")
async def list_models(
    org: str | None = Query(None, description="Filter by organization"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = _session,  # noqa: B008
):
    """List tracked AI models."""
    from .services.model_lifecycle import list_tracked_models

    models = await list_tracked_models(session, organization=org, limit=limit)
    return _to_dict(models)


@router.get("/models/{slug}")
async def get_model(
    slug: str,
    session: AsyncSession = _session,  # noqa: B008
):
    """Get detailed profile for a specific model."""
    from .services.model_lifecycle import build_model_profile

    profile = await build_model_profile(session, slug)
    if profile is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return _to_dict(profile)


@router.get("/models/{slug}/timeline")
async def get_model_timeline(
    slug: str,
    session: AsyncSession = _session,  # noqa: B008
):
    """Get event timeline for a specific model."""
    from .services.model_lifecycle import get_model_timeline as _get_timeline

    timeline = await _get_timeline(session, slug)
    return _to_dict(timeline)


@router.get("/benchmarks")
async def list_benchmarks(
    session: AsyncSession = _session,  # noqa: B008
):
    """List all tracked benchmarks."""
    from .services.benchmark_trends import list_benchmarks as _list_benchmarks

    benchmarks = await _list_benchmarks(session)
    return _to_dict(benchmarks)


@router.get("/benchmarks/{name}")
async def get_benchmark_leaderboard(
    name: str,
    session: AsyncSession = _session,  # noqa: B008
):
    """Get leaderboard for a specific benchmark."""
    from .services.benchmark_trends import get_benchmark_leaderboard as _get_leaderboard

    leaderboard = await _get_leaderboard(session, name)
    return _to_dict(leaderboard)


@router.get("/benchmarks/{name}/timeline")
async def get_benchmark_timeline(
    name: str,
    model: str | None = Query(None, description="Filter by model slug"),
    session: AsyncSession = _session,  # noqa: B008
):
    """Get benchmark score time series."""
    from .services.benchmark_trends import get_benchmark_timeline as _get_timeline

    timeline = await _get_timeline(session, name, model_slug=model)
    return _to_dict(timeline)


@router.get("/competitive")
async def get_competitive_timeline(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = _session,  # noqa: B008
):
    """Get cross-org competitive activity timeline."""
    from .services.competitive_intel import get_activity_timeline

    timeline = await get_activity_timeline(session, window_days=days)
    return _to_dict(timeline)


@router.get("/research")
async def get_research_trends(
    days: int = Query(90, ge=1, le=365),
    session: AsyncSession = _session,  # noqa: B008
):
    """Get research pulse: trends, citations, paper-to-product links."""
    from .services.research_pulse import get_research_trends as _get_trends

    trends = await _get_trends(session, window_days=days)
    return _to_dict(trends)


@router.get("/insights")
async def get_insights(
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = _session,  # noqa: B008
):
    """Get recent analysis insights."""
    from .services.anomaly_detector import get_recent_insights

    insights = await get_recent_insights(session, limit=limit, severity=severity)
    return [
        {
            "id": i.id,
            "insight_type": i.insight_type,
            "severity": i.severity,
            "title": i.title,
            "description": i.description,
            "related_model_slug": i.related_model_slug,
            "related_org": i.related_org,
            "detected_at": str(i.detected_at) if i.detected_at else None,
        }
        for i in insights
    ]


@router.get("/digest")
async def get_digest(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = _session,  # noqa: B008
):
    """Generate a digest without persisting."""
    from .services.digest import generate_digest

    report = await generate_digest(session, window_days=days, persist=False)
    return _to_dict(report)


@router.post("/digest")
async def create_digest(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = _session,  # noqa: B008
):
    """Generate and persist a digest."""
    from .services.digest import generate_digest

    report = await generate_digest(session, window_days=days, persist=True)
    await session.commit()
    return _to_dict(report)


@router.get("/spotlight")
async def get_spotlight_report(
    days: int = Query(30, ge=1, le=365),
    min_benchmarks: int = Query(1, ge=0),
    org: str | None = Query(None),
    session: AsyncSession = _session,  # noqa: B008
):
    """New models ranked by benchmark performance."""
    from .services.spotlight import get_spotlight

    report = await get_spotlight(
        session, window_days=days, min_benchmarks=min_benchmarks, organization=org
    )
    return _to_dict(report)


@router.get("/evolution")
async def get_evolution(
    benchmark: str | None = Query(None),
    days: int = Query(180, ge=1, le=730),
    session: AsyncSession = _session,  # noqa: B008
):
    """Benchmark evolution and frontier progression."""
    from .services.evolution import get_benchmark_evolution

    summaries = await get_benchmark_evolution(session, benchmark_name=benchmark, window_days=days)
    return [_to_dict(s) for s in summaries]


@router.get("/capability/{slug}")
async def get_capability(
    slug: str,
    session: AsyncSession = _session,  # noqa: B008
):
    """Cross-benchmark capability profile for a model."""
    from .services.capability import get_capability_profile

    profile = await get_capability_profile(session, slug)
    if profile is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
    return _to_dict(profile)


@router.get("/capability")
async def compare_capability(
    models: str = Query(..., description="Comma-separated model slugs"),
    session: AsyncSession = _session,  # noqa: B008
):
    """Compare capability profiles for multiple models."""
    from .services.capability import compare_capabilities

    slugs = [s.strip() for s in models.split(",")]
    profiles = await compare_capabilities(session, slugs)
    return [_to_dict(p) for p in profiles]


@router.get("/landscape")
async def get_landscape_report(
    days: int = Query(30, ge=1, le=365),
    org: str | None = Query(None),
    session: AsyncSession = _session,  # noqa: B008
):
    """Competitive landscape with benchmark context."""
    from .services.landscape import get_landscape

    report = await get_landscape(session, window_days=days, organization=org)
    return _to_dict(report)


@router.get("/research-pipeline")
async def get_research_pipeline_report(
    days: int = Query(90, ge=1, le=365),
    min_citations: int = Query(0, ge=0),
    session: AsyncSession = _session,  # noqa: B008
):
    """Research-to-product pipeline: citation velocity, topic trends, predictive signals."""
    from .services.research_pipeline import get_research_pipeline

    report = await get_research_pipeline(session, window_days=days, min_citations=min_citations)
    return _to_dict(report)
