"""Tests for Phase 8 refinements: scoring weights, section balance, comparison, HTML export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.formatters.html import edition_to_html
from ai_benchmark.publication.services.edition import compare_editions, generate_edition
from ai_benchmark.publication.services.scoring import _WEIGHTS, _resolve_weights
from ai_benchmark.publication.services.sectioning import assign_sections
from ai_benchmark.publication.types import (
    CandidateItem,
    EditionResult,
    EntryResult,
    ScoredCandidate,
    SectionResult,
)


def _make_settings(**overrides) -> PublicationSettings:
    defaults = {"_env_file": None, "cutoff_hour": 23}
    defaults.update(overrides)
    return PublicationSettings(**defaults)  # type: ignore[call-arg]


# --- Scoring Weight Override Tests ---


def test_resolve_weights_default():
    settings = _make_settings()
    weights = _resolve_weights(settings)
    assert weights == _WEIGHTS


def test_resolve_weights_with_overrides():
    settings = _make_settings(scoring_weight_overrides='{"recency": 0.3, "novelty": 0.05}')
    weights = _resolve_weights(settings)
    assert weights["recency"] == 0.3
    assert weights["novelty"] == 0.05
    # Unchanged keys stay default
    assert weights["verification"] == _WEIGHTS["verification"]


def test_resolve_weights_ignores_unknown_keys():
    settings = _make_settings(scoring_weight_overrides='{"unknown_key": 0.5}')
    weights = _resolve_weights(settings)
    assert "unknown_key" not in weights
    assert weights == _WEIGHTS


# --- Section Balance Tests ---


def _make_sc(event_type: str, score: float, org: str = "OrgA") -> ScoredCandidate:
    return ScoredCandidate(
        candidate=CandidateItem(
            event_id=1,
            paper_id=None,
            title=f"Test {event_type} by {org}",
            organization=org,
            model_slug=None,
            benchmark_name=None,
            event_type=event_type,
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=1,
            cross_ref_count=0,
            observed_at=datetime.now(UTC).isoformat(),
            raw_content=None,
        ),
        score=score,
    )


@pytest.mark.asyncio
async def test_section_org_diversity_constraint():
    settings = _make_settings(max_org_pct_per_section=0.5)
    scored = [
        _make_sc("model_release", 0.9, "OrgA"),
        _make_sc("model_release", 0.8, "OrgA"),
        _make_sc("model_release", 0.7, "OrgA"),
    ]
    sections = await assign_sections(scored, settings)
    # With 50% cap, at most 1 out of 2 items can be from same org
    # First item passes (1/1 = 100% but section is empty so it's 1/(0+1)=100% > 50%)
    # Actually the check is: org_count / (len + 1) > max_pct
    # When section has 1 item (OrgA), adding 2nd OrgA: 1/2 = 50% — not > 50%, so passes
    # When section has 2 items (both OrgA), adding 3rd: 2/3 = 67% > 50%, goes to watchlist
    announcements = sections["announcements"]
    watchlist = sections["watchlist"]
    assert len(announcements) == 2
    assert len(watchlist) == 1


@pytest.mark.asyncio
async def test_section_watchlist_promotion():
    settings = _make_settings(min_items_per_section=1, max_items_per_section=5)
    # All items are news, no announcements
    scored = [
        _make_sc("news", 0.3),
        _make_sc("news", 0.2),
    ]
    sections = await assign_sections(scored, settings)
    # Both go to industry_news, but min_items_per_section=1 doesn't
    # promote since there's nothing in watchlist for other sections
    assert len(sections["industry_news"]) == 2


# --- HTML Export Tests ---


def test_html_export_basic():
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[
            SectionResult(
                section_key="announcements",
                title="Announcements",
                entries=[
                    EntryResult(
                        entry_id=1,
                        rank=1,
                        title="GPT-5 Released",
                        summary="OpenAI releases GPT-5.",
                        why_it_matters="Major capability jump.",
                        entry_type="model_release",
                        organization="OpenAI",
                        model_slug="gpt-5",
                        benchmark_name=None,
                        verification_status="confirmed",
                        confidence_summary="official_self_report",
                        source_count=3,
                        score=0.95,
                        event_id=1,
                        paper_id=None,
                    )
                ],
                summary="One announcement.",
            )
        ],
        summary="Test edition.",
        stats={},
    )
    html = edition_to_html(edition)
    assert "<!DOCTYPE html>" in html
    assert "GPT-5 Released" in html
    assert "OpenAI" in html
    assert "confirmed" in html
    assert "Why it matters" in html


def test_html_export_escapes():
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[
            SectionResult(
                section_key="test",
                title="Test <script>",
                entries=[
                    EntryResult(
                        entry_id=1,
                        rank=1,
                        title='Title with "quotes" & <tags>',
                        summary="Summary.",
                        why_it_matters=None,
                        entry_type="news",
                        organization=None,
                        model_slug=None,
                        benchmark_name=None,
                        verification_status="unconfirmed",
                        confidence_summary=None,
                        source_count=1,
                        score=0.5,
                        event_id=1,
                        paper_id=None,
                    )
                ],
                summary="",
            )
        ],
        summary="",
        stats={},
    )
    html = edition_to_html(edition)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "&quot;" in html


def test_html_export_empty():
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[],
        summary="Nothing.",
        stats={},
    )
    html = edition_to_html(edition)
    assert "<!DOCTYPE html>" in html
    assert "Nothing." in html


# --- Edition Comparison Tests ---


@pytest.fixture
async def two_editions(db_session):
    """Generate two editions on different dates."""
    now = datetime.now(UTC)
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

    # Event in both windows
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
        observed_at=now - timedelta(hours=3),
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
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    await generate_edition(db_session, publication_date=today, settings=settings)
    await generate_edition(db_session, publication_date=yesterday, settings=settings)
    await db_session.flush()

    return today, yesterday


@pytest.mark.asyncio
async def test_compare_editions(db_session, two_editions):
    today, yesterday = two_editions
    result = await compare_editions(db_session, yesterday, today)
    assert result["date_a"] == yesterday
    assert result["date_b"] == today
    assert "common_count" in result
    assert isinstance(result["new_entries"], list)
    assert isinstance(result["removed_entries"], list)


@pytest.mark.asyncio
async def test_compare_editions_not_found(db_session):
    result = await compare_editions(db_session, "2020-01-01", "2020-01-02")
    assert "error" in result
