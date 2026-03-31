"""Tests for publication candidate assembly, scoring, and sectioning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, CrossReference, EventRecord
from ai_benchmark.models.research import EnrichedPaper
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.services.assembly import assemble_candidates
from ai_benchmark.publication.services.scoring import score_candidates
from ai_benchmark.publication.services.sectioning import assign_sections
from ai_benchmark.publication.types import CandidateItem, ScoredCandidate

# --- Fixtures ---


def _make_settings(**overrides) -> PublicationSettings:
    defaults = {"_env_file": None}
    defaults.update(overrides)
    return PublicationSettings(**defaults)  # type: ignore[call-arg]


@pytest.fixture
async def source_and_page(db_session):
    source = Source(
        source_name="OpenAI",
        category="official",
        organization="OpenAI",
        homepage_url="https://openai.com/",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="primary",
        classification="primary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://openai.com/news/",
        page_type="product-news",
        polling_frequency="daily",
    )
    db_session.add(page)
    await db_session.flush()
    return source, page


@pytest.fixture
async def benchmark_source(db_session):
    source = Source(
        source_name="LMArena",
        category="benchmark",
        organization="LMArena",
        homepage_url="https://lmarena.ai/",
        base_domain="lmarena.ai",
        trust_rating=4.0,
        source_role="primary",
        classification="secondary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()
    return source


# --- Assembly Tests ---


@pytest.mark.asyncio
async def test_assemble_basic_event(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)
    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 Released",
        normalized_title="gpt-5 released",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/gpt-5",
        event_type="model_release",
        model_slug="gpt-5",
        observed_at=now - timedelta(hours=6),
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="GPT-5 released",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 1
    assert candidates[0].title == "GPT-5 Released"
    assert candidates[0].verification_status == "confirmed"
    assert candidates[0].source_count == 1


@pytest.mark.asyncio
async def test_assemble_excludes_conflicted(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)
    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="Conflicted Event",
        normalized_title="conflicted event",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/conflict",
        event_type="model_release",
        observed_at=now - timedelta(hours=3),
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="Conflicted claim",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="medium_discovery",
        confirmation_status="conflicted",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_assemble_includes_conflicted_when_configured(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)
    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="Conflicted Event",
        normalized_title="conflicted event",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/conflict",
        event_type="model_release",
        observed_at=now - timedelta(hours=3),
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="Conflicted",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="medium_discovery",
        confirmation_status="conflicted",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings(include_low_confidence=True)
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 1
    assert candidates[0].verification_status == "conflicted"


@pytest.mark.asyncio
async def test_assemble_benchmark_requires_owner_claim(
    db_session, source_and_page, benchmark_source
):
    source, page = source_and_page
    now = datetime.now(UTC)

    # Benchmark event with only medium_discovery claim — should be excluded
    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 tops SWE-bench",
        normalized_title="gpt-5 tops swe-bench",
        organization="OpenAI",
        source_type="benchmark",
        canonical_path="https://openai.com/benchmark",
        event_type="benchmark_result",
        model_slug="gpt-5",
        benchmark_variant="swe-bench-verified",
        observed_at=now - timedelta(hours=3),
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="GPT-5 scored 72% on SWE-bench",
        source_type="news",
        source_name="TechCrunch",
        confidence_tier="medium_discovery",
        confirmation_status="unconfirmed",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 0

    # Now add benchmark-owner claim — should be included
    owner_claim = ClaimRecord(
        event_id=ev.id,
        claim_text="GPT-5 scored 72% on SWE-bench Verified",
        source_type="benchmark",
        source_name="SWE-bench",
        confidence_tier="benchmark_owner_report",
        confirmation_status="confirmed",
    )
    db_session.add(owner_claim)
    await db_session.flush()

    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 1
    assert candidates[0].benchmark_name == "swe-bench-verified"


@pytest.mark.asyncio
async def test_assemble_pricing_requires_official_claim(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)

    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 Price Drop",
        normalized_title="gpt-5 price drop",
        organization="OpenAI",
        source_type="pricing",
        canonical_path="https://openai.com/pricing",
        event_type="pricing_change",
        model_slug="gpt-5",
        observed_at=now - timedelta(hours=5),
    )
    db_session.add(ev)
    await db_session.flush()

    # Only secondary claim — should be excluded
    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="Price drop reported",
        source_type="news",
        source_name="Reuters",
        confidence_tier="high_secondary",
        confirmation_status="unconfirmed",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_assemble_research_papers(db_session):
    now = datetime.now(UTC)
    paper = EnrichedPaper(
        title="Scaling Laws for Reasoning",
        arxiv_id="2603.12345",
        authors="Jane Doe, John Smith",
        abstract="We study scaling laws for reasoning.",
        citation_count=42,
        venue="NeurIPS 2026",
        enriched_at=now - timedelta(hours=8),
    )
    db_session.add(paper)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 1
    assert candidates[0].event_type == "research"
    assert candidates[0].paper_id == paper.id
    assert candidates[0].analysis_signals["citation_count"] == 42


@pytest.mark.asyncio
async def test_assemble_deduplicates_events(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)

    # Two events with same dedup key
    for i in range(2):
        ev = EventRecord(
            source_id=source.id,
            page_id=page.id,
            title="GPT-5 Released",
            normalized_title="gpt-5 released",
            organization="OpenAI",
            source_type="product-news",
            canonical_path=f"https://openai.com/news/gpt-5-{i}",
            event_type="model_release",
            model_slug="gpt-5",
            observed_at=now - timedelta(hours=6 + i),
        )
        db_session.add(ev)
        await db_session.flush()

        claim = ClaimRecord(
            event_id=ev.id,
            claim_text="GPT-5 released",
            source_type="product-news",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        )
        db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_assemble_empty_window(db_session):
    now = datetime.now(UTC)
    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    assert candidates == []


@pytest.mark.asyncio
async def test_assemble_counts_cross_refs(db_session, source_and_page):
    source, page = source_and_page
    now = datetime.now(UTC)

    ev1 = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 Released",
        normalized_title="gpt-5 released",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/gpt-5",
        event_type="model_release",
        model_slug="gpt-5",
        observed_at=now - timedelta(hours=6),
    )
    ev2 = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 Benchmarks",
        normalized_title="gpt-5 benchmarks",
        organization="OpenAI",
        source_type="benchmark",
        canonical_path="https://openai.com/benchmarks",
        event_type="benchmark_update",
        model_slug="gpt-5",
        observed_at=now - timedelta(hours=5),
    )
    db_session.add_all([ev1, ev2])
    await db_session.flush()

    # Add claims for ev1
    claim = ClaimRecord(
        event_id=ev1.id,
        claim_text="GPT-5 released",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
    )
    db_session.add(claim)

    xref = CrossReference(
        record_a_id=ev1.id,
        record_b_id=ev2.id,
        relationship_type="confirms",
    )
    db_session.add(xref)
    await db_session.flush()

    settings = _make_settings()
    candidates = await assemble_candidates(
        db_session,
        window_start=now - timedelta(days=1),
        window_end=now,
        settings=settings,
    )
    # ev1 should have cross_ref_count >= 1
    model_release = [c for c in candidates if c.event_type == "model_release"]
    assert len(model_release) == 1
    assert model_release[0].cross_ref_count >= 1


# --- Scoring Tests ---


@pytest.mark.asyncio
async def test_scoring_deterministic():
    settings = _make_settings()
    candidates = [
        CandidateItem(
            event_id=1,
            paper_id=None,
            title="High priority",
            organization="OpenAI",
            model_slug="gpt-5",
            benchmark_name=None,
            event_type="model_release",
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=3,
            cross_ref_count=2,
            observed_at=datetime.now(UTC).isoformat(),
            raw_content=None,
        ),
        CandidateItem(
            event_id=2,
            paper_id=None,
            title="Low priority",
            organization="TestCo",
            model_slug=None,
            benchmark_name=None,
            event_type="news",
            verification_status="unconfirmed",
            confidence_tier="low_discovery",
            source_count=1,
            cross_ref_count=0,
            observed_at=datetime.now(UTC).isoformat(),
            raw_content=None,
        ),
    ]

    scored1 = await score_candidates(candidates, settings)
    scored2 = await score_candidates(candidates, settings)

    assert [s.score for s in scored1] == [s.score for s in scored2]
    assert scored1[0].score > scored1[1].score


@pytest.mark.asyncio
async def test_scoring_verified_beats_unverified():
    settings = _make_settings()
    now = datetime.now(UTC).isoformat()
    candidates = [
        CandidateItem(
            event_id=1,
            paper_id=None,
            title="Verified",
            organization="A",
            model_slug=None,
            benchmark_name=None,
            event_type="model_release",
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=1,
            cross_ref_count=0,
            observed_at=now,
            raw_content=None,
        ),
        CandidateItem(
            event_id=2,
            paper_id=None,
            title="Unverified",
            organization="B",
            model_slug=None,
            benchmark_name=None,
            event_type="model_release",
            verification_status="unconfirmed",
            confidence_tier="low_discovery",
            source_count=1,
            cross_ref_count=0,
            observed_at=now,
            raw_content=None,
        ),
    ]
    scored = await score_candidates(candidates, settings)
    assert scored[0].candidate.title == "Verified"


@pytest.mark.asyncio
async def test_scoring_weights_sum_to_one():
    from ai_benchmark.publication.services.scoring import _WEIGHTS

    assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9


# --- Sectioning Tests ---


@pytest.mark.asyncio
async def test_sectioning_maps_types():
    settings = _make_settings()
    now = datetime.now(UTC).isoformat()

    def _make_sc(event_type: str, score: float) -> ScoredCandidate:
        return ScoredCandidate(
            candidate=CandidateItem(
                event_id=1,
                paper_id=None,
                title=f"Test {event_type}",
                organization="TestOrg",
                model_slug=None,
                benchmark_name=None,
                event_type=event_type,
                verification_status="confirmed",
                confidence_tier="official_self_report",
                source_count=1,
                cross_ref_count=0,
                observed_at=now,
                raw_content=None,
            ),
            score=score,
        )

    scored = [
        _make_sc("benchmark_result", 0.9),
        _make_sc("model_release", 0.8),
        _make_sc("research", 0.7),
        _make_sc("news", 0.6),
    ]

    sections = await assign_sections(scored, settings)
    assert len(sections["benchmark_movers"]) == 1
    assert len(sections["announcements"]) == 1
    assert len(sections["research_pulse"]) == 1
    assert len(sections["industry_news"]) == 1


@pytest.mark.asyncio
async def test_sectioning_overflow_to_watchlist():
    settings = _make_settings(max_items_per_section=1)
    now = datetime.now(UTC).isoformat()

    scored = [
        ScoredCandidate(
            candidate=CandidateItem(
                event_id=i,
                paper_id=None,
                title=f"Release {i}",
                organization="Org",
                model_slug=None,
                benchmark_name=None,
                event_type="model_release",
                verification_status="confirmed",
                confidence_tier="official_self_report",
                source_count=1,
                cross_ref_count=0,
                observed_at=now,
                raw_content=None,
            ),
            score=0.9 - i * 0.1,
        )
        for i in range(3)
    ]

    sections = await assign_sections(scored, settings)
    assert len(sections["announcements"]) == 1
    assert len(sections["watchlist"]) == 2


@pytest.mark.asyncio
async def test_sectioning_low_score_to_watchlist():
    settings = _make_settings(min_score_threshold=0.5)
    now = datetime.now(UTC).isoformat()

    scored = [
        ScoredCandidate(
            candidate=CandidateItem(
                event_id=1,
                paper_id=None,
                title="Low score",
                organization="Org",
                model_slug=None,
                benchmark_name=None,
                event_type="model_release",
                verification_status="confirmed",
                confidence_tier="official_self_report",
                source_count=1,
                cross_ref_count=0,
                observed_at=now,
                raw_content=None,
            ),
            score=0.3,
        )
    ]

    sections = await assign_sections(scored, settings)
    assert len(sections["announcements"]) == 0
    assert len(sections["watchlist"]) == 1


@pytest.mark.asyncio
async def test_sectioning_top_summary_populated():
    settings = _make_settings()
    now = datetime.now(UTC).isoformat()

    scored = [
        ScoredCandidate(
            candidate=CandidateItem(
                event_id=i,
                paper_id=None,
                title=f"Item {i}",
                organization="Org",
                model_slug=None,
                benchmark_name=None,
                event_type=["benchmark_result", "model_release", "research", "news", "news"][i],
                verification_status="confirmed",
                confidence_tier="official_self_report",
                source_count=1,
                cross_ref_count=0,
                observed_at=now,
                raw_content=None,
            ),
            score=0.9 - i * 0.1,
        )
        for i in range(5)
    ]

    sections = await assign_sections(scored, settings)
    assert len(sections["top_summary"]) == 3
    assert sections["top_summary"][0].score >= sections["top_summary"][1].score
