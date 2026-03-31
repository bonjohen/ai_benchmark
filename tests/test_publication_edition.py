"""Tests for the edition generation pipeline (end-to-end)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.research import EnrichedPaper
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.models import PublicationEdition, PublicationEntry, PublicationSection
from ai_benchmark.publication.services.edition import generate_edition
from ai_benchmark.publication.services.render import (
    render_edition_summary,
    render_entry_text,
    render_section_summary,
)
from ai_benchmark.publication.types import CandidateItem, ScoredCandidate


def _make_settings(**overrides) -> PublicationSettings:
    defaults = {"_env_file": None, "cutoff_hour": 23}
    defaults.update(overrides)
    return PublicationSettings(**defaults)  # type: ignore[call-arg]


@pytest.fixture
async def populated_db(db_session):
    """Seed DB with events, claims, and papers within today's window."""
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

    # Model release event
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
        observed_at=now - timedelta(hours=3),
        raw_content="OpenAI releases GPT-5.",
    )
    db_session.add(ev1)
    await db_session.flush()

    claim1 = ClaimRecord(
        event_id=ev1.id,
        claim_text="GPT-5 released",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
    )
    db_session.add(claim1)

    # Research paper
    paper = EnrichedPaper(
        title="Scaling Laws for Reasoning",
        arxiv_id="2603.12345",
        authors="Jane Doe",
        abstract="We study scaling laws.",
        citation_count=10,
        venue="NeurIPS 2026",
        enriched_at=now - timedelta(hours=5),
    )
    db_session.add(paper)
    await db_session.flush()

    return {"source": source, "page": page, "event": ev1, "paper": paper}


# --- Edition Generation Tests ---


@pytest.mark.asyncio
async def test_generate_edition_full(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    result = await generate_edition(db_session, publication_date=today, settings=settings)

    assert result.edition_id is not None
    assert result.publication_date == today
    assert result.summary != ""
    assert result.stats["total_entries"] >= 1
    assert result.stats["total_candidates"] >= 1

    # At least one section should have entries
    non_empty = [s for s in result.sections if s.entries]
    assert len(non_empty) >= 1


@pytest.mark.asyncio
async def test_generate_edition_persists(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    result = await generate_edition(db_session, publication_date=today, settings=settings)
    await db_session.commit()

    # Verify DB records exist
    from sqlalchemy import select

    ed_result = await db_session.execute(
        select(PublicationEdition).where(PublicationEdition.publication_date == today)
    )
    edition = ed_result.scalar_one()
    assert edition.id == result.edition_id
    assert edition.status == "draft"
    assert edition.summary_text is not None

    sec_result = await db_session.execute(
        select(PublicationSection).where(PublicationSection.edition_id == edition.id)
    )
    sections = sec_result.scalars().all()
    assert len(sections) >= 1

    ent_result = await db_session.execute(
        select(PublicationEntry).where(PublicationEntry.edition_id == edition.id)
    )
    entries = ent_result.scalars().all()
    assert len(entries) >= 1


@pytest.mark.asyncio
async def test_generate_edition_idempotent_draft(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    result1 = await generate_edition(db_session, publication_date=today, settings=settings)
    await db_session.commit()

    # Regenerate — should delete and recreate (SQLite may reuse IDs)
    result2 = await generate_edition(db_session, publication_date=today, settings=settings)
    await db_session.commit()

    assert result2.edition_id is not None
    assert result2.stats["total_entries"] == result1.stats["total_entries"]


@pytest.mark.asyncio
async def test_generate_edition_frozen_rejects(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    await generate_edition(db_session, publication_date=today, settings=settings)

    # Freeze the edition
    from sqlalchemy import select

    ed_result = await db_session.execute(
        select(PublicationEdition).where(PublicationEdition.publication_date == today)
    )
    edition = ed_result.scalar_one()
    edition.status = "frozen"
    edition.frozen_at = datetime.now(UTC)
    await db_session.flush()

    with pytest.raises(ValueError, match="frozen"):
        await generate_edition(db_session, publication_date=today, settings=settings)


@pytest.mark.asyncio
async def test_generate_edition_empty_day(db_session):
    settings = _make_settings()
    result = await generate_edition(db_session, publication_date="2020-01-01", settings=settings)
    assert result.stats["total_entries"] == 0
    assert result.summary != ""


@pytest.mark.asyncio
async def test_generate_edition_entry_text_fields(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    result = await generate_edition(db_session, publication_date=today, settings=settings)

    for section in result.sections:
        for entry in section.entries:
            assert entry.title != ""
            assert entry.summary != ""
            # why_it_matters may be empty for some types but should be present
            assert entry.why_it_matters is not None


# --- Render Unit Tests ---


def test_render_edition_summary_with_items():
    sc = ScoredCandidate(
        candidate=CandidateItem(
            event_id=1,
            paper_id=None,
            title="GPT-5 Released",
            organization="OpenAI",
            model_slug="gpt-5",
            benchmark_name=None,
            event_type="model_release",
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=1,
            cross_ref_count=0,
            observed_at="2026-03-30T12:00:00",
            raw_content=None,
        ),
        score=0.9,
    )
    summary = render_edition_summary({"top_summary": [sc]})
    assert "OpenAI" in summary
    assert "gpt-5" in summary


def test_render_edition_summary_empty():
    summary = render_edition_summary({"top_summary": []})
    assert "No significant" in summary


def test_render_section_summary():
    sc = ScoredCandidate(
        candidate=CandidateItem(
            event_id=1,
            paper_id=None,
            title="Test",
            organization="Org",
            model_slug=None,
            benchmark_name=None,
            event_type="model_release",
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=1,
            cross_ref_count=0,
            observed_at="2026-03-30T12:00:00",
            raw_content=None,
        ),
        score=0.5,
    )
    summary = render_section_summary("announcements", [sc])
    assert "1" in summary or "One" in summary


def test_render_entry_text_confirmed():
    sc = ScoredCandidate(
        candidate=CandidateItem(
            event_id=1,
            paper_id=None,
            title="GPT-5 Released",
            organization="OpenAI",
            model_slug="gpt-5",
            benchmark_name=None,
            event_type="model_release",
            verification_status="confirmed",
            confidence_tier="official_self_report",
            source_count=3,
            cross_ref_count=2,
            observed_at="2026-03-30T12:00:00",
            raw_content=None,
        ),
        score=0.9,
    )
    text = render_entry_text(sc)
    assert text["title"] == "GPT-5 Released"
    assert "OpenAI" in text["summary"]
    assert "Confirmed" in text["why_it_matters"]
    assert "cross-reference" in text["why_it_matters"]
