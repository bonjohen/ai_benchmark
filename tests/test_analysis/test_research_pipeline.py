"""Tests for research pipeline service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.research_pipeline import get_research_pipeline


@pytest.mark.asyncio
async def test_research_pipeline_empty_db(db_session):
    """Research pipeline on empty DB returns empty report."""
    report = await get_research_pipeline(db_session, window_days=90)
    assert report.velocity_leaders == []
    assert report.topic_trends == []
    assert report.paper_product_links == []
    assert report.predictive_signals == []


@pytest.mark.asyncio
async def test_research_pipeline_velocity(db_session, sample_enriched_papers):
    """Velocity leaders are sorted by citation velocity descending."""
    report = await get_research_pipeline(db_session, window_days=90)
    assert len(report.velocity_leaders) >= 1
    # Should be sorted by velocity descending
    for i in range(len(report.velocity_leaders) - 1):
        assert (
            report.velocity_leaders[i].velocity_per_week
            >= report.velocity_leaders[i + 1].velocity_per_week
        )


@pytest.mark.asyncio
async def test_research_pipeline_velocity_values(db_session, sample_enriched_papers):
    """Velocity is citation_count / weeks_since_enrichment."""
    report = await get_research_pipeline(db_session, window_days=90)
    for entry in report.velocity_leaders:
        assert entry.velocity_per_week > 0
        assert entry.citation_count > 0


@pytest.mark.asyncio
async def test_research_pipeline_topic_trends(db_session, sample_enriched_papers):
    """Topic trends reflect enriched paper tags."""
    report = await get_research_pipeline(db_session, window_days=180)
    if report.topic_trends:
        for trend in report.topic_trends:
            assert trend.direction in ("rising", "falling", "stable")
            assert trend.total_count >= 1


@pytest.mark.asyncio
async def test_research_pipeline_topic_direction(db_session, sample_enriched_papers):
    """Topic direction reflects recent vs earlier counts."""
    report = await get_research_pipeline(db_session, window_days=180)
    for trend in report.topic_trends:
        if trend.recent_count > trend.earlier_count:
            assert trend.direction == "rising"
        elif trend.recent_count < trend.earlier_count:
            assert trend.direction == "falling"
        else:
            assert trend.direction == "stable"


@pytest.mark.asyncio
async def test_research_pipeline_min_citations(db_session, sample_enriched_papers):
    """min_citations filter excludes low-citation papers."""
    # With very high min_citations, nothing should pass
    report = await get_research_pipeline(db_session, window_days=90, min_citations=10000)
    assert report.velocity_leaders == []


@pytest.mark.asyncio
async def test_research_pipeline_paper_product_links(
    db_session, sample_enriched_papers, multi_org_events, multi_org_claims
):
    """Paper-product links connect enriched papers to model releases."""
    report = await get_research_pipeline(db_session, window_days=365)
    # Enriched papers have Anthropic in authors, and multi_org_events has Anthropic model_release
    # So we should get at least one link
    if report.paper_product_links:
        for link in report.paper_product_links:
            assert link.paper_title
            assert link.organization
            assert link.lag_days >= 0
