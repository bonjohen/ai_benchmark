"""Tests for SemanticScholarCollector."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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

    mock_results = [{
        "title": "LLM Evaluation Framework",
        "url": "https://semanticscholar.org/paper/123",
        "abstract": "We present a framework for evaluating language models.",
        "authors": [{"name": "Alice"}, {"name": "Bob"}],
        "paperId": "s2_123",
        "externalIds": {"ArXiv": "2603.12345"},
        "citationCount": 42,
    }]

    with patch.object(collector.client, "search_paper", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        items = await collector.collect_via_api(["LLM evaluation"], limit=5)

    assert len(items) == 1
    assert items[0].item_type == "candidate_paper"
    assert items[0].title == "LLM Evaluation Framework"
    assert items[0].metadata["arxiv_id"] == "2603.12345"
    assert items[0].metadata["source"] == "semantic_scholar"
    assert items[0].metadata["authors"] == "Alice, Bob"
