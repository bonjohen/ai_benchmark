"""Tests for publication scheduler integration, health tracking, static export, and regeneration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.models import PublicationEdition
from ai_benchmark.publication.scheduler import PublicationHealthTracker
from ai_benchmark.publication.services.edition import (
    check_regeneration_eligible,
    generate_edition,
)
from ai_benchmark.publication.services.export import export_static
from ai_benchmark.publication.types import EditionResult, EntryResult, SectionResult

# --- Fixtures ---


def _make_settings(**overrides) -> PublicationSettings:
    defaults = {"_env_file": None, "cutoff_hour": 23}
    defaults.update(overrides)
    return PublicationSettings(**defaults)  # type: ignore[call-arg]


@pytest.fixture
async def populated_db(db_session):
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

    return {"source": source, "page": page, "event": ev}


# --- Health Tracker Tests ---


def test_health_tracker_initial_state():
    tracker = PublicationHealthTracker()
    status = tracker.get_status()
    assert status["consecutive_failures"] == 0
    assert status["last_generated_at"] is None
    assert status["total_runs"] == 0


def test_health_tracker_record_success():
    tracker = PublicationHealthTracker()
    tracker.record_success("2026-03-30")
    status = tracker.get_status()
    assert status["consecutive_failures"] == 0
    assert status["last_publication_date"] == "2026-03-30"
    assert status["total_runs"] == 1
    assert status["total_successes"] == 1


def test_health_tracker_record_failure():
    tracker = PublicationHealthTracker()
    tracker.record_failure("DB timeout")
    status = tracker.get_status()
    assert status["consecutive_failures"] == 1
    assert status["last_error"] == "DB timeout"
    assert status["total_runs"] == 1
    assert status["total_successes"] == 0


def test_health_tracker_success_resets_failures():
    tracker = PublicationHealthTracker()
    tracker.record_failure("err1")
    tracker.record_failure("err2")
    assert tracker.get_status()["consecutive_failures"] == 2

    tracker.record_success("2026-03-30")
    assert tracker.get_status()["consecutive_failures"] == 0
    assert tracker.get_status()["last_error"] is None


# --- Static Export Tests ---


@pytest.mark.asyncio
async def test_export_static_markdown(tmp_path):
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
                        title="Test",
                        summary="A test.",
                        why_it_matters=None,
                        entry_type="model_release",
                        organization="Org",
                        model_slug=None,
                        benchmark_name=None,
                        verification_status="confirmed",
                        confidence_summary="official_self_report",
                        source_count=1,
                        score=0.5,
                        event_id=1,
                        paper_id=None,
                    )
                ],
                summary="One item.",
            )
        ],
        summary="Test edition.",
        stats={"total_entries": 1},
    )
    written = await export_static(edition, str(tmp_path), formats=["markdown"])
    assert len(written) == 1
    assert written[0].endswith(".md")

    content = (tmp_path / "edition-2026-03-30.md").read_text(encoding="utf-8")
    assert "Daily AI Benchmark" in content


@pytest.mark.asyncio
async def test_export_static_json(tmp_path):
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[],
        summary="Empty.",
        stats={},
    )
    written = await export_static(edition, str(tmp_path), formats=["json"])
    assert len(written) == 1
    assert written[0].endswith(".json")


@pytest.mark.asyncio
async def test_export_static_both(tmp_path):
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[],
        summary="Both.",
        stats={},
    )
    written = await export_static(edition, str(tmp_path))
    assert len(written) == 2


# --- Regeneration Eligibility Tests ---


@pytest.mark.asyncio
async def test_regeneration_not_eligible_no_edition(db_session):
    settings = _make_settings()
    eligible = await check_regeneration_eligible(db_session, "2020-01-01", settings)
    assert eligible is False


@pytest.mark.asyncio
async def test_regeneration_not_eligible_frozen(db_session, populated_db):
    settings = _make_settings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await generate_edition(db_session, publication_date=today, settings=settings)

    from sqlalchemy import select

    ed_result = await db_session.execute(
        select(PublicationEdition).where(PublicationEdition.publication_date == today)
    )
    edition = ed_result.scalar_one()
    edition.status = "frozen"
    edition.frozen_at = datetime.now(UTC)
    await db_session.flush()

    eligible = await check_regeneration_eligible(db_session, today, settings)
    assert eligible is False


@pytest.mark.asyncio
async def test_regeneration_eligible_new_high_confidence(db_session, populated_db):
    settings = _make_settings(auto_freeze_delay_hours=24)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await generate_edition(db_session, publication_date=today, settings=settings)

    # Add a new high-confidence event after generation
    source_data = populated_db
    now = datetime.now(UTC)
    ev = EventRecord(
        source_id=source_data["source"].id,
        page_id=source_data["page"].id,
        title="GPT-5 Turbo Released",
        normalized_title="gpt-5 turbo released",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/gpt-5-turbo",
        event_type="model_release",
        model_slug="gpt-5-turbo",
        observed_at=now,
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="GPT-5 Turbo released",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
    )
    db_session.add(claim)
    await db_session.flush()

    eligible = await check_regeneration_eligible(db_session, today, settings)
    assert eligible is True

    # Verify status updated
    from sqlalchemy import select

    ed_result = await db_session.execute(
        select(PublicationEdition).where(PublicationEdition.publication_date == today)
    )
    edition = ed_result.scalar_one()
    assert edition.status == "regeneration_available"
