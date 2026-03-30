"""Tests for SemanticScholarCollector."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.sources.registry import get_collector
from ai_benchmark.sources.research.semantic_scholar import SemanticScholarCollector


def _make_config() -> SourceConfig:
    return SourceConfig(
        source_name="Semantic Scholar",
        category="research",
        organization="Semantic Scholar",
        homepage_url="https://www.semanticscholar.org",
        base_domain="semanticscholar.org",
        trust_rating=4.0,
        source_role="enrichment",
        classification="secondary",
        pages=[],
    )


def test_collector_instantiation():
    """SemanticScholarCollector can be instantiated."""
    config = _make_config()
    collector = SemanticScholarCollector(config)
    assert collector.source_config.organization == "Semantic Scholar"


def test_collector_extract_items_returns_empty():
    """extract_items returns empty list (API-only source)."""
    config = _make_config()
    collector = SemanticScholarCollector(config)
    page = PageConfig(canonical_url="https://www.semanticscholar.org", page_type="api")
    items = collector.extract_items("<html></html>", page)
    assert items == []


def test_collector_in_registry():
    """SemanticScholarCollector is retrievable via get_collector."""
    config = _make_config()
    collector = get_collector(config)
    assert isinstance(collector, SemanticScholarCollector)


@pytest.mark.asyncio
async def test_collect_via_api_returns_raw_items():
    """collect_via_api returns RawItem objects with correct item_type."""
    config = _make_config()
    collector = SemanticScholarCollector(config)

    mock_results = [
        {
            "title": "LLM Evaluation Framework",
            "url": "https://semanticscholar.org/paper/123",
            "abstract": "We present a framework for evaluating language models.",
            "authors": [{"name": "Alice"}, {"name": "Bob"}],
            "paperId": "s2_123",
            "externalIds": {"ArXiv": "2603.12345"},
            "citationCount": 42,
        }
    ]

    with patch.object(collector.client, "search_paper", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        items = await collector.collect_via_api(["LLM evaluation"], limit=5)

    assert len(items) == 1
    assert items[0].item_type == "candidate_paper"
    assert items[0].title == "LLM Evaluation Framework"
    assert items[0].metadata["arxiv_id"] == "2603.12345"
    assert items[0].metadata["source"] == "semantic_scholar"
    assert items[0].metadata["authors"] == "Alice, Bob"


@pytest.mark.asyncio
async def test_collect_via_api_inter_query_delay():
    """Inter-query delay is applied between queries."""
    config = _make_config()
    collector = SemanticScholarCollector(config)

    mock_results = [
        {
            "title": "Paper A",
            "url": "https://semanticscholar.org/paper/a",
            "abstract": "",
            "authors": [],
            "paperId": "a",
            "externalIds": {},
            "citationCount": 0,
        }
    ]

    call_count = 0

    async def mock_search(query, limit=5):
        nonlocal call_count
        call_count += 1
        return mock_results

    with (
        patch.object(collector.client, "search_paper", side_effect=mock_search),
        patch("ai_benchmark.sources.research.semantic_scholar.asyncio.sleep") as mock_sleep,
    ):
        items = await collector.collect_via_api(["q1", "q2", "q3"], limit=1)

    assert call_count == 3
    assert len(items) == 3
    # Sleep called between queries (not before first)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(3.0)


@pytest.mark.asyncio
async def test_collect_via_api_per_query_error_handling():
    """A failing query doesn't prevent other queries from running."""
    config = _make_config()
    collector = SemanticScholarCollector(config)

    good_result = [
        {
            "title": "Good Paper",
            "url": "https://semanticscholar.org/paper/good",
            "abstract": "",
            "authors": [],
            "paperId": "good",
            "externalIds": {},
            "citationCount": 0,
        }
    ]

    async def mock_search(query, limit=5):
        if query == "bad_query":
            raise RuntimeError("API error")
        return good_result

    with (
        patch.object(collector.client, "search_paper", side_effect=mock_search),
        patch("ai_benchmark.sources.research.semantic_scholar.asyncio.sleep"),
    ):
        items = await collector.collect_via_api(["good1", "bad_query", "good2"], limit=1)

    assert len(items) == 2
    assert all(i.title == "Good Paper" for i in items)


@pytest.mark.asyncio
async def test_collect_page_logs_missing_api_key():
    """collect_page logs warning when API key is not set."""
    config = _make_config()
    collector = SemanticScholarCollector(config, api_key=None)

    page = PageConfig(canonical_url="https://api.semanticscholar.org/graph/v1", page_type="api")
    fetcher = MagicMock()
    snapshot_mgr = MagicMock()

    with (
        patch.object(collector, "collect_via_api", new_callable=AsyncMock, return_value=[]),
        patch("ai_benchmark.sources.research.semantic_scholar.logger") as mock_logger,
    ):
        items, diff = await collector.collect_page(page, fetcher, snapshot_mgr, page_id=1)

    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert call_args[0][0] == "semantic_scholar_no_api_key"
    assert items == []
