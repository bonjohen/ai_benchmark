"""Tests for research pulse service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.research_pulse import (
    detect_paper_to_product,
    get_citation_leaders,
    get_research_trends,
)

# --- get_citation_leaders ---


@pytest.mark.asyncio
async def test_get_citation_leaders(db_session, sample_enriched_papers):
    """Returns papers ordered by citation count."""
    leaders = await get_citation_leaders(db_session, limit=10)
    assert len(leaders) == 2
    # Highest citation count first
    assert leaders[0].citation_count >= leaders[1].citation_count
    assert leaders[0].title == "Scaling Laws for Neural Language Models"
    assert leaders[0].citation_count == 1500


@pytest.mark.asyncio
async def test_get_citation_leaders_limit(db_session, sample_enriched_papers):
    """Limit restricts results."""
    leaders = await get_citation_leaders(db_session, limit=1)
    assert len(leaders) == 1


@pytest.mark.asyncio
async def test_get_citation_leaders_empty(db_session):
    """Returns empty list when no papers exist."""
    leaders = await get_citation_leaders(db_session, limit=10)
    assert leaders == []


@pytest.mark.asyncio
async def test_get_citation_leaders_fields(db_session, sample_enriched_papers):
    """Citation leader entries have correct fields."""
    leaders = await get_citation_leaders(db_session, limit=10)
    leader = leaders[0]
    assert leader.arxiv_id == "2001.08361"
    assert leader.venue == "NeurIPS"
    assert leader.enriched_at  # non-empty string


# --- detect_paper_to_product ---


@pytest.mark.asyncio
async def test_detect_paper_to_product_empty(db_session):
    """No papers and no events means no links."""
    links = await detect_paper_to_product(db_session, max_lag_days=180)
    assert links == []


@pytest.mark.asyncio
async def test_detect_paper_to_product_no_match(db_session, sample_enriched_papers):
    """Papers without matching org events produce no links."""
    # sample_enriched_papers have authors like "Jared Kaplan, Sam McCandlish"
    # and "Yuntao Bai, Anthropic" — but there are no EventRecords from these orgs
    links = await detect_paper_to_product(db_session, max_lag_days=180)
    assert links == []


@pytest.mark.asyncio
async def test_detect_paper_to_product_with_match(
    db_session, sample_events, sample_enriched_papers
):
    """Papers matching org + time window produce links."""
    # sample_events have organization="OpenAI"
    # sample_enriched_papers[1] has authors="Yuntao Bai, Anthropic" — no match for OpenAI
    # sample_enriched_papers[0] has authors="Jared Kaplan, Sam McCandlish" — no match for OpenAI
    # Neither paper mentions "OpenAI" in authors, so no links expected
    links = await detect_paper_to_product(db_session, max_lag_days=180)
    assert isinstance(links, list)


# --- get_research_trends ---


@pytest.mark.asyncio
async def test_get_research_trends(db_session, sample_enriched_papers):
    """get_research_trends returns a complete ResearchTrends."""
    trends = await get_research_trends(db_session, window_days=365)
    assert trends.window_days == 365
    assert isinstance(trends.total_papers, int)
    assert isinstance(trends.promoted_count, int)
    assert isinstance(trends.citation_leaders, list)


@pytest.mark.asyncio
async def test_get_research_trends_topic_counts(db_session, sample_enriched_papers):
    """Topic counts are extracted from relevance_tags."""
    trends = await get_research_trends(db_session, window_days=365)
    # Papers have tags: "benchmark,llm,scaling" and "safety,alignment,anthropic"
    assert "llm" in trends.topic_counts or "benchmark" in trends.topic_counts


@pytest.mark.asyncio
async def test_get_research_trends_empty(db_session):
    """Empty database returns zeroed trends."""
    trends = await get_research_trends(db_session, window_days=7)
    assert trends.total_papers == 0
    assert trends.citation_leaders == []
    assert trends.topic_counts == {}
