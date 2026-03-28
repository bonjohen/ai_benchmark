"""Tests for the research triage pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_benchmark.models.research import CandidatePaper, EnrichedPaper
from ai_benchmark.processing.triage import (
    enrich_candidate,
    get_pending_candidates,
    ingest_candidate,
    promote_to_enriched,
)


@pytest.mark.asyncio
async def test_ingest_candidate_creates_record(db_session):
    paper = await ingest_candidate(
        db_session,
        title="New Benchmark for LLM Evaluation",
        arxiv_id="2603.12345",
        authors="Smith, Jones",
        categories="cs.AI",
        abstract_url="https://arxiv.org/abs/2603.12345",
        discovered_via="arxiv",
    )
    assert paper is not None
    assert paper.title == "New Benchmark for LLM Evaluation"
    assert paper.arxiv_id == "2603.12345"
    assert paper.status == "pending"


@pytest.mark.asyncio
async def test_ingest_candidate_skips_duplicate(db_session):
    await ingest_candidate(
        db_session,
        title="Duplicate Paper",
        arxiv_id="2603.99999",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="arxiv",
    )
    result = await ingest_candidate(
        db_session,
        title="Duplicate Paper Again",
        arxiv_id="2603.99999",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="hf_papers",
    )
    assert result is None


@pytest.mark.asyncio
async def test_ingest_candidate_no_arxiv_id(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Paper Without arXiv ID",
        arxiv_id=None,
        authors="Unknown",
        categories=None,
        abstract_url=None,
        discovered_via="hf_papers",
    )
    assert paper is not None
    assert paper.arxiv_id is None


@pytest.mark.asyncio
async def test_enrich_candidate_marks_relevant(db_session):
    paper = await ingest_candidate(
        db_session,
        title="LLM Benchmark Evaluation",
        arxiv_id="2603.11111",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="arxiv",
    )

    mock_client = AsyncMock()
    mock_client.get_paper_by_arxiv.return_value = {
        "title": "LLM Benchmark Evaluation for Language Models",
        "abstract": "We present a new benchmark for evaluating large language model performance on reasoning tasks.",
        "paperId": "abc123",
    }

    result = await enrich_candidate(db_session, paper, mock_client)
    assert result.status == "enriched"


@pytest.mark.asyncio
async def test_enrich_candidate_rejects_irrelevant(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Quantum Computing Methods",
        arxiv_id="2603.22222",
        authors="Physicist",
        categories="physics.QC",
        abstract_url=None,
        discovered_via="arxiv",
    )

    mock_client = AsyncMock()
    mock_client.get_paper_by_arxiv.return_value = {
        "title": "Quantum Computing Methods for Solid State Physics",
        "abstract": "A novel approach to quantum computing using superconducting circuits.",
        "paperId": "def456",
    }

    result = await enrich_candidate(db_session, paper, mock_client)
    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_enrich_candidate_api_failure_stays_pending(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Some Paper",
        arxiv_id="2603.33333",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="arxiv",
    )

    mock_client = AsyncMock()
    mock_client.get_paper_by_arxiv.side_effect = Exception("API timeout")

    result = await enrich_candidate(db_session, paper, mock_client)
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_enrich_candidate_no_arxiv_searches_by_title(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Agent Safety Alignment Study",
        arxiv_id=None,
        authors="Author",
        categories=None,
        abstract_url=None,
        discovered_via="hf_papers",
    )

    mock_client = AsyncMock()
    mock_client.search_paper.return_value = [{
        "title": "Agent Safety Alignment Study for LLM Systems",
        "abstract": "A comprehensive evaluation of safety alignment techniques for language model agents.",
        "paperId": "ghi789",
    }]

    result = await enrich_candidate(db_session, paper, mock_client)
    assert result.status == "enriched"
    mock_client.search_paper.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_candidate_no_arxiv_no_results_rejects(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Obscure Paper",
        arxiv_id=None,
        authors="Author",
        categories=None,
        abstract_url=None,
        discovered_via="hf_papers",
    )

    mock_client = AsyncMock()
    mock_client.search_paper.return_value = []

    result = await enrich_candidate(db_session, paper, mock_client)
    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_promote_to_enriched(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Promoted Paper",
        arxiv_id="2603.44444",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="arxiv",
    )
    paper.status = "enriched"

    paper_data = {
        "title": "Promoted Paper: Full Title",
        "paperId": "s2_id_123",
        "abstract": "This paper presents...",
        "authors": [{"name": "Alice"}, {"name": "Bob"}],
        "venue": "NeurIPS 2026",
        "citationCount": 42,
        "externalIds": {"GitHub": "https://github.com/example/repo"},
    }

    enriched = await promote_to_enriched(db_session, paper, paper_data)
    assert isinstance(enriched, EnrichedPaper)
    assert enriched.semantic_scholar_id == "s2_id_123"
    assert enriched.authors == "Alice, Bob"
    assert enriched.citation_count == 42
    assert enriched.code_url == "https://github.com/example/repo"
    assert enriched.venue == "NeurIPS 2026"
    assert paper.status == "promoted"


@pytest.mark.asyncio
async def test_get_pending_candidates(db_session):
    for i in range(5):
        await ingest_candidate(
            db_session,
            title=f"Pending Paper {i}",
            arxiv_id=f"2603.{50000 + i}",
            authors="Author",
            categories="cs.AI",
            abstract_url=None,
            discovered_via="arxiv",
        )
    await db_session.flush()

    pending = await get_pending_candidates(db_session, limit=3)
    assert len(pending) == 3
    assert all(p.status == "pending" for p in pending)


@pytest.mark.asyncio
async def test_get_pending_candidates_excludes_enriched(db_session):
    paper = await ingest_candidate(
        db_session,
        title="Already Enriched",
        arxiv_id="2603.60000",
        authors="Author",
        categories="cs.AI",
        abstract_url=None,
        discovered_via="arxiv",
    )
    paper.status = "enriched"
    await db_session.flush()

    pending = await get_pending_candidates(db_session)
    ids = [p.arxiv_id for p in pending]
    assert "2603.60000" not in ids
