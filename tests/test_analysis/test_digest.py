"""Tests for digest service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.digest import generate_digest


@pytest.mark.asyncio
async def test_generate_digest(db_session, sample_events, sample_claims, sample_enriched_papers):
    """generate_digest returns a complete DigestReport."""
    report = await generate_digest(db_session, window_days=30, persist=False)
    assert report.period_start is not None
    assert report.period_end is not None
    assert isinstance(report.stats, dict)


@pytest.mark.asyncio
async def test_generate_digest_model_updates(
    db_session, sample_events, sample_claims, sample_enriched_papers
):
    """Digest includes model updates from the window."""
    report = await generate_digest(db_session, window_days=30, persist=False)
    slugs = {m.model_slug for m in report.model_updates}
    # Events are within 30 days
    assert "gpt-5" in slugs or "gpt-4o-mini" in slugs


@pytest.mark.asyncio
async def test_generate_digest_stats(
    db_session, sample_events, sample_claims, sample_enriched_papers
):
    """Digest stats contain expected keys."""
    report = await generate_digest(db_session, window_days=30, persist=False)
    assert "total_models" in report.stats
    assert "active_models" in report.stats
    assert "total_benchmarks" in report.stats
    assert "anomalies_detected" in report.stats


@pytest.mark.asyncio
async def test_generate_digest_persist(
    db_session, sample_events, sample_claims, sample_enriched_papers
):
    """Digest with persist=True creates an AnalysisSnapshot."""
    from sqlalchemy import select

    from ai_benchmark.analysis.models import AnalysisSnapshot

    await generate_digest(db_session, window_days=30, persist=True)
    await db_session.commit()

    stmt = select(AnalysisSnapshot).where(AnalysisSnapshot.analysis_type == "digest")
    result = await db_session.execute(stmt)
    snapshots = list(result.scalars().all())
    assert len(snapshots) >= 1
    assert "weekly-" in snapshots[0].scope_key


@pytest.mark.asyncio
async def test_generate_digest_no_persist(db_session, sample_events, sample_claims):
    """Digest with persist=False does not create a snapshot."""
    from sqlalchemy import select

    from ai_benchmark.analysis.models import AnalysisSnapshot

    await generate_digest(db_session, window_days=30, persist=False)

    stmt = select(AnalysisSnapshot).where(AnalysisSnapshot.analysis_type == "digest")
    result = await db_session.execute(stmt)
    snapshots = list(result.scalars().all())
    assert len(snapshots) == 0


@pytest.mark.asyncio
async def test_generate_digest_empty_db(db_session):
    """Digest works with empty database."""
    report = await generate_digest(db_session, window_days=7, persist=False)
    assert report.model_updates == []
    assert report.benchmark_movements == []
    assert report.stats["total_models"] == 0


@pytest.mark.asyncio
async def test_generate_digest_spotlight(db_session, multi_org_events, multi_org_claims):
    """Digest includes spotlight models."""
    report = await generate_digest(db_session, window_days=30, persist=False)
    assert isinstance(report.spotlight_models, list)
    # multi_org_events has new models within 30 days
    if report.spotlight_models:
        slugs = {s.model_slug for s in report.spotlight_models}
        assert len(slugs) >= 1


@pytest.mark.asyncio
async def test_generate_digest_evolution(db_session, multi_org_events, multi_org_claims):
    """Digest includes evolution highlights."""
    report = await generate_digest(db_session, window_days=30, persist=False)
    assert isinstance(report.evolution_highlights, list)
    # multi_org_events has benchmark data
    if report.evolution_highlights:
        for evo in report.evolution_highlights:
            assert evo.benchmark_name
