"""Shared fixtures for analysis pipeline tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.research import EnrichedPaper
from ai_benchmark.models.sources import Page, Source


@pytest.fixture
async def sample_source(db_session):
    """Create a sample source record."""
    source = Source(
        source_name="OpenAI",
        category="official company source",
        organization="OpenAI",
        homepage_url="https://openai.com/",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="primary source",
        classification="primary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest.fixture
async def sample_page(db_session, sample_source):
    """Create a sample page record."""
    page = Page(
        source_id=sample_source.id,
        canonical_url="https://openai.com/news/",
        page_type="product-news index",
        polling_frequency="daily",
    )
    db_session.add(page)
    await db_session.flush()
    return page


@pytest.fixture
async def sample_events(db_session, sample_source, sample_page):
    """Create a set of sample events for different models and types."""
    now = datetime.now(UTC)
    events = [
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 Released",
            normalized_title="gpt-5 released",
            organization="OpenAI",
            source_type="product-news index",
            canonical_path="https://openai.com/news/gpt-5",
            published_date="2026-03-15",
            event_type="model_release",
            model_slug="gpt-5",
            observed_at=now - timedelta(days=14),
            raw_content="OpenAI releases GPT-5 with scored 95.2% on benchmarks",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 Pricing Update",
            normalized_title="gpt-5 pricing update",
            organization="OpenAI",
            source_type="pricing",
            canonical_path="https://openai.com/pricing",
            published_date="2026-03-16",
            event_type="pricing_change",
            model_slug="gpt-5",
            observed_at=now - timedelta(days=13),
            raw_content="GPT-5 pricing: $5 per million input tokens",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 on SWE-bench Verified",
            normalized_title="gpt-5 on swe-bench verified",
            organization="OpenAI",
            source_type="leaderboard",
            canonical_path="https://swebench.com/verified",
            published_date="2026-03-17",
            event_type="announcement",
            model_slug="gpt-5",
            benchmark_variant="SWE-bench Verified",
            observed_at=now - timedelta(days=12),
            raw_content="GPT-5 achieves 72.3% on SWE-bench Verified",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-4o Mini Deprecated",
            normalized_title="gpt-4o mini deprecated",
            organization="OpenAI",
            source_type="changelog",
            canonical_path="https://platform.openai.com/docs/changelog",
            published_date="2026-03-20",
            event_type="deprecation",
            model_slug="gpt-4o-mini",
            observed_at=now - timedelta(days=9),
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()
    return events


@pytest.fixture
async def sample_claims(db_session, sample_events):
    """Create claims for sample events."""
    claims = [
        ClaimRecord(
            event_id=sample_events[0].id,
            claim_text="GPT-5 Released",
            source_type="product-news index",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        ClaimRecord(
            event_id=sample_events[0].id,
            claim_text="GPT-5 launch confirmed",
            source_type="changelog",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        ClaimRecord(
            event_id=sample_events[1].id,
            claim_text="GPT-5 Pricing Update",
            source_type="pricing",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        ClaimRecord(
            event_id=sample_events[2].id,
            claim_text="GPT-5 on SWE-bench",
            source_type="leaderboard",
            source_name="SWE-bench team",
            confidence_tier="benchmark_owner_report",
            confirmation_status="unconfirmed",
        ),
    ]
    db_session.add_all(claims)
    await db_session.flush()
    return claims


@pytest.fixture
async def sample_enriched_papers(db_session):
    """Create sample enriched papers."""
    papers = [
        EnrichedPaper(
            candidate_id=None,
            title="Scaling Laws for Neural Language Models",
            arxiv_id="2001.08361",
            authors="Jared Kaplan, Sam McCandlish",
            abstract="We study empirical scaling laws for language model performance.",
            venue="NeurIPS",
            citation_count=1500,
            relevance_tags="benchmark,llm,scaling",
            enriched_at=datetime.now(UTC) - timedelta(days=30),
        ),
        EnrichedPaper(
            candidate_id=None,
            title="Constitutional AI: Harmlessness from AI Feedback",
            arxiv_id="2212.08073",
            authors="Yuntao Bai, Anthropic",
            abstract="We propose a method for training harmless AI assistants.",
            venue="ICML",
            citation_count=800,
            relevance_tags="safety,alignment,anthropic",
            enriched_at=datetime.now(UTC) - timedelta(days=60),
        ),
    ]
    db_session.add_all(papers)
    await db_session.flush()
    return papers
