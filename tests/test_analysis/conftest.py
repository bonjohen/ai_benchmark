"""Shared fixtures for analysis pipeline tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, CrossReference, EventRecord
from ai_benchmark.models.research import CandidatePaper, EnrichedPaper
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
async def anthropic_source(db_session):
    """Create a second organization (Anthropic) source record."""
    source = Source(
        source_name="Anthropic",
        category="official company source",
        organization="Anthropic",
        homepage_url="https://www.anthropic.com/",
        base_domain="anthropic.com",
        trust_rating=5.0,
        source_role="primary source",
        classification="primary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest.fixture
async def anthropic_page(db_session, anthropic_source):
    """Create a page for Anthropic."""
    page = Page(
        source_id=anthropic_source.id,
        canonical_url="https://www.anthropic.com/news/",
        page_type="product-news index",
        polling_frequency="daily",
    )
    db_session.add(page)
    await db_session.flush()
    return page


@pytest.fixture
async def multi_org_events(
    db_session, sample_source, sample_page, anthropic_source, anthropic_page
):
    """Create events for both OpenAI and Anthropic with benchmark scores."""
    now = datetime.now(UTC)
    events = [
        # OpenAI GPT-5 events
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
            raw_content="OpenAI releases GPT-5",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 SWE-bench Score",
            normalized_title="gpt-5 swe-bench score",
            organization="OpenAI",
            source_type="leaderboard",
            canonical_path="https://swebench.com/verified",
            published_date="2026-03-17",
            event_type="announcement",
            model_slug="gpt-5",
            benchmark_variant="SWE-bench Verified",
            observed_at=now - timedelta(days=12),
            raw_content="GPT-5 scored 92.3% on SWE-bench Verified",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 MMLU Score",
            normalized_title="gpt-5 mmlu score",
            organization="OpenAI",
            source_type="leaderboard",
            canonical_path="https://openai.com/research/gpt-5-mmlu",
            published_date="2026-03-17",
            event_type="announcement",
            model_slug="gpt-5",
            benchmark_variant="MMLU",
            observed_at=now - timedelta(days=12),
            raw_content="GPT-5 achieves Score: 95.1% on MMLU",
        ),
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-5 Pricing",
            normalized_title="gpt-5 pricing drop",
            organization="OpenAI",
            source_type="pricing",
            canonical_path="https://openai.com/pricing",
            published_date="2026-03-18",
            event_type="pricing_change",
            model_slug="gpt-5",
            observed_at=now - timedelta(days=11),
            raw_content="GPT-5 pricing drop to $5 per million tokens, a decrease from $15",
        ),
        # Anthropic Claude-4-sonnet events
        EventRecord(
            source_id=anthropic_source.id,
            page_id=anthropic_page.id,
            title="Claude 4 Sonnet Released",
            normalized_title="claude 4 sonnet released",
            organization="Anthropic",
            source_type="product-news index",
            canonical_path="https://www.anthropic.com/news/claude-4-sonnet",
            published_date="2026-03-16",
            event_type="model_release",
            model_slug="claude-4-sonnet",
            observed_at=now - timedelta(days=13),
            raw_content="Anthropic releases Claude 4 Sonnet",
        ),
        EventRecord(
            source_id=anthropic_source.id,
            page_id=anthropic_page.id,
            title="Claude 4 Sonnet SWE-bench Score",
            normalized_title="claude 4 sonnet swe-bench score",
            organization="Anthropic",
            source_type="leaderboard",
            canonical_path="https://swebench.com/verified",
            published_date="2026-03-18",
            event_type="announcement",
            model_slug="claude-4-sonnet",
            benchmark_variant="SWE-bench Verified",
            observed_at=now - timedelta(days=11),
            raw_content="Claude 4 Sonnet achieved 89.7% on SWE-bench Verified",
        ),
        EventRecord(
            source_id=anthropic_source.id,
            page_id=anthropic_page.id,
            title="Claude 4 Sonnet MMLU Score",
            normalized_title="claude 4 sonnet mmlu score",
            organization="Anthropic",
            source_type="leaderboard",
            canonical_path="https://www.anthropic.com/research/mmlu",
            published_date="2026-03-18",
            event_type="announcement",
            model_slug="claude-4-sonnet",
            benchmark_variant="MMLU",
            observed_at=now - timedelta(days=11),
            raw_content="Claude 4 Sonnet achieves 91.2% on MMLU",
        ),
        # Older event to test evolution frontier
        EventRecord(
            source_id=sample_source.id,
            page_id=sample_page.id,
            title="GPT-4o SWE-bench Score",
            normalized_title="gpt-4o swe-bench score",
            organization="OpenAI",
            source_type="leaderboard",
            canonical_path="https://swebench.com/verified",
            published_date="2026-01-15",
            event_type="announcement",
            model_slug="gpt-4o",
            benchmark_variant="SWE-bench Verified",
            observed_at=now - timedelta(days=73),
            raw_content="GPT-4o scored 71.5% on SWE-bench Verified",
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()
    return events


@pytest.fixture
async def multi_org_claims(db_session, multi_org_events):
    """Create claims at multiple confidence tiers for multi-org events."""
    claims = [
        # GPT-5 release — confirmed by two sources
        ClaimRecord(
            event_id=multi_org_events[0].id,
            claim_text="GPT-5 Released",
            source_type="product-news index",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        ClaimRecord(
            event_id=multi_org_events[0].id,
            claim_text="GPT-5 launch confirmed by Reuters",
            source_type="wire service",
            source_name="Reuters",
            confidence_tier="high_secondary",
            confirmation_status="confirmed",
        ),
        # GPT-5 SWE-bench — benchmark owner report
        ClaimRecord(
            event_id=multi_org_events[1].id,
            claim_text="GPT-5 92.3% on SWE-bench Verified",
            source_type="leaderboard",
            source_name="SWE-bench team",
            confidence_tier="benchmark_owner_report",
            confirmation_status="confirmed",
        ),
        # GPT-5 MMLU — unconfirmed
        ClaimRecord(
            event_id=multi_org_events[2].id,
            claim_text="GPT-5 95.1% on MMLU",
            source_type="leaderboard",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="unconfirmed",
        ),
        # GPT-5 Pricing
        ClaimRecord(
            event_id=multi_org_events[3].id,
            claim_text="GPT-5 pricing decrease",
            source_type="pricing",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        # Claude-4-sonnet release — confirmed
        ClaimRecord(
            event_id=multi_org_events[4].id,
            claim_text="Claude 4 Sonnet Released",
            source_type="product-news index",
            source_name="Anthropic",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        ),
        # Claude-4-sonnet SWE-bench — conflicted (for verification testing)
        ClaimRecord(
            event_id=multi_org_events[5].id,
            claim_text="Claude 4 Sonnet 89.7% on SWE-bench",
            source_type="leaderboard",
            source_name="SWE-bench team",
            confidence_tier="benchmark_owner_report",
            confirmation_status="conflicted",
        ),
        # Claude-4-sonnet MMLU
        ClaimRecord(
            event_id=multi_org_events[6].id,
            claim_text="Claude 4 Sonnet 91.2% on MMLU",
            source_type="leaderboard",
            source_name="Anthropic",
            confidence_tier="official_self_report",
            confirmation_status="unconfirmed",
        ),
    ]
    db_session.add_all(claims)
    await db_session.flush()
    return claims


@pytest.fixture
async def multi_org_xrefs(db_session, multi_org_events):
    """Create cross-references between events."""
    xrefs = [
        # GPT-5 release confirmed by SWE-bench announcement
        CrossReference(
            record_a_id=multi_org_events[0].id,
            record_b_id=multi_org_events[1].id,
            relationship_type="confirms",
        ),
        # GPT-5 MMLU supplements the release
        CrossReference(
            record_a_id=multi_org_events[0].id,
            record_b_id=multi_org_events[2].id,
            relationship_type="supplements",
        ),
        # Claude-4-sonnet release confirmed by SWE-bench
        CrossReference(
            record_a_id=multi_org_events[4].id,
            record_b_id=multi_org_events[5].id,
            relationship_type="confirms",
        ),
    ]
    db_session.add_all(xrefs)
    await db_session.flush()
    return xrefs


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


@pytest.fixture
async def sample_candidate_papers(db_session):
    """Create sample candidate papers for research pipeline tests."""
    papers = [
        CandidatePaper(
            title="Scaling Laws for Neural Language Models",
            arxiv_id="2001.08361",
            authors="Jared Kaplan",
            categories="cs.CL",
            discovered_via="arxiv",
            status="promoted",
            discovered_at=datetime.now(UTC) - timedelta(days=30),
        ),
        CandidatePaper(
            title="Constitutional AI",
            arxiv_id="2212.08073",
            authors="Yuntao Bai",
            categories="cs.AI",
            discovered_via="arxiv",
            status="promoted",
            discovered_at=datetime.now(UTC) - timedelta(days=60),
        ),
        CandidatePaper(
            title="Rejected Paper",
            arxiv_id="9999.99999",
            authors="Nobody",
            categories="cs.AI",
            discovered_via="arxiv",
            status="rejected",
            discovered_at=datetime.now(UTC) - timedelta(days=10),
        ),
        CandidatePaper(
            title="Pending Paper",
            arxiv_id="8888.88888",
            authors="Someone",
            categories="cs.CL",
            discovered_via="hf_papers",
            status="pending",
            discovered_at=datetime.now(UTC) - timedelta(days=5),
        ),
    ]
    db_session.add_all(papers)
    await db_session.flush()
    return papers
