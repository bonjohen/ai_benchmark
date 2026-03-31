"""Tests for publication pipeline ORM models and configuration."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.models import (
    PublicationAuditLog,
    PublicationEdition,
    PublicationEntry,
    PublicationSection,
)
from ai_benchmark.publication.types import (
    CandidateItem,
    EditionResult,
    EntryResult,
    ScoredCandidate,
    SectionResult,
)

# --- ORM Model Tests ---


@pytest.mark.asyncio
async def test_edition_creation(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
        status="draft",
        generation_version=1,
        summary_text="Test summary for 2026-03-30 edition.",
    )
    db_session.add(edition)
    await db_session.flush()

    assert edition.id is not None
    assert edition.generated_at is not None
    assert edition.status == "draft"
    assert edition.frozen_at is None
    assert edition.published_at is None


@pytest.mark.asyncio
async def test_edition_unique_date(db_session):
    edition1 = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition1)
    await db_session.flush()

    edition2 = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_section_creation(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition)
    await db_session.flush()

    section = PublicationSection(
        edition_id=edition.id,
        section_key="benchmark_movers",
        title="Benchmark Movers",
        rank=1,
        item_count=0,
        generated_summary="Notable benchmark changes today.",
    )
    db_session.add(section)
    await db_session.flush()

    assert section.id is not None
    assert section.edition_id == edition.id


@pytest.mark.asyncio
async def test_entry_creation(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition)
    await db_session.flush()

    section = PublicationSection(
        edition_id=edition.id,
        section_key="announcements",
        title="Model & Vendor Announcements",
        rank=2,
    )
    db_session.add(section)
    await db_session.flush()

    entry = PublicationEntry(
        edition_id=edition.id,
        section_id=section.id,
        rank=1,
        entry_type="model_release",
        title_generated="GPT-5 Released",
        title_final="GPT-5 Released",
        summary_generated="OpenAI releases GPT-5 with improved reasoning.",
        summary_final="OpenAI releases GPT-5 with improved reasoning.",
        why_it_matters_generated="Major capability jump in reasoning tasks.",
        why_it_matters_final="Major capability jump in reasoning tasks.",
        score=0.95,
        org_slug="openai",
        model_slug="gpt-5",
        verification_status="confirmed",
        confidence_summary="official_self_report",
        source_count=3,
    )
    db_session.add(entry)
    await db_session.flush()

    assert entry.id is not None
    assert entry.is_pinned is False
    assert entry.is_suppressed is False
    assert entry.is_overridden is False
    assert entry.created_at is not None


@pytest.mark.asyncio
async def test_audit_log_creation(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition)
    await db_session.flush()

    log = PublicationAuditLog(
        edition_id=edition.id,
        entry_id=None,
        action_type="freeze",
        actor="admin@example.com",
        before_state_json='{"status": "draft"}',
        after_state_json='{"status": "frozen"}',
    )
    db_session.add(log)
    await db_session.flush()

    assert log.id is not None
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_edition_section_relationship(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition)
    await db_session.flush()

    s1 = PublicationSection(
        edition_id=edition.id, section_key="benchmark_movers", title="Benchmark Movers", rank=1
    )
    s2 = PublicationSection(
        edition_id=edition.id, section_key="announcements", title="Announcements", rank=2
    )
    db_session.add_all([s1, s2])
    await db_session.flush()

    result = await db_session.execute(
        select(PublicationSection).where(PublicationSection.edition_id == edition.id)
    )
    sections = result.scalars().all()
    assert len(sections) == 2


@pytest.mark.asyncio
async def test_edition_cascade_delete(db_session):
    edition = PublicationEdition(
        publication_date="2026-03-30",
        window_start=datetime(2026, 3, 29, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 30, 6, 0, tzinfo=UTC),
    )
    db_session.add(edition)
    await db_session.flush()

    section = PublicationSection(
        edition_id=edition.id, section_key="watchlist", title="Watchlist", rank=5
    )
    db_session.add(section)
    await db_session.flush()

    entry = PublicationEntry(
        edition_id=edition.id,
        section_id=section.id,
        rank=1,
        entry_type="model_release",
        title_generated="Test",
        title_final="Test",
        summary_generated="Summary",
        summary_final="Summary",
        score=0.5,
    )
    db_session.add(entry)
    await db_session.flush()

    log = PublicationAuditLog(edition_id=edition.id, action_type="generate", actor="system")
    db_session.add(log)
    await db_session.flush()

    await db_session.delete(edition)
    await db_session.flush()

    result = await db_session.execute(select(PublicationSection))
    assert len(result.scalars().all()) == 0

    result = await db_session.execute(select(PublicationEntry))
    assert len(result.scalars().all()) == 0

    result = await db_session.execute(select(PublicationAuditLog))
    assert len(result.scalars().all()) == 0


# --- Config Tests ---


def test_publication_settings_defaults():
    settings = PublicationSettings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.cutoff_hour == 6
    assert settings.timezone == "US/Pacific"
    assert settings.max_items_per_section == 10
    assert settings.min_score_threshold == 0.1
    assert settings.include_low_confidence is False
    assert settings.auto_freeze_delay_hours == 12
    assert settings.export_path is None
    assert settings.archive_retention_days == 90
    assert settings.html_mode == "dynamic"


def test_publication_settings_overrides(monkeypatch):
    monkeypatch.setenv("AI_BENCH_PUB_CUTOFF_HOUR", "8")
    monkeypatch.setenv("AI_BENCH_PUB_MAX_ITEMS_PER_SECTION", "5")
    monkeypatch.setenv("AI_BENCH_PUB_MIN_SCORE_THRESHOLD", "0.25")
    monkeypatch.setenv("AI_BENCH_PUB_INCLUDE_LOW_CONFIDENCE", "true")
    monkeypatch.setenv("AI_BENCH_PUB_EXPORT_PATH", "/tmp/pub_export")

    settings = PublicationSettings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.cutoff_hour == 8
    assert settings.max_items_per_section == 5
    assert settings.min_score_threshold == 0.25
    assert settings.include_low_confidence is True
    assert settings.export_path == "/tmp/pub_export"


# --- Dataclass Tests ---


def test_candidate_item_creation():
    c = CandidateItem(
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
    )
    assert c.event_id == 1
    assert c.analysis_signals == {}


def test_scored_candidate_creation():
    c = CandidateItem(
        event_id=1,
        paper_id=None,
        title="Test",
        organization="TestOrg",
        model_slug=None,
        benchmark_name=None,
        event_type="model_release",
        verification_status="unconfirmed",
        confidence_tier="medium_discovery",
        source_count=1,
        cross_ref_count=0,
        observed_at="2026-03-30T12:00:00",
        raw_content=None,
    )
    sc = ScoredCandidate(candidate=c, score=0.72, score_breakdown={"recency": 0.1})
    assert sc.score == 0.72
    assert sc.section_key == ""


def test_edition_result_creation():
    entry = EntryResult(
        entry_id=1,
        rank=1,
        title="Test Entry",
        summary="A test.",
        why_it_matters=None,
        entry_type="model_release",
        organization="TestOrg",
        model_slug="test-model",
        benchmark_name=None,
        verification_status="confirmed",
        confidence_summary="official_self_report",
        source_count=2,
        score=0.85,
        event_id=1,
        paper_id=None,
    )
    section = SectionResult(
        section_key="announcements",
        title="Model & Vendor Announcements",
        entries=[entry],
        summary="One announcement today.",
    )
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[section],
        summary="Test edition.",
        stats={"total_entries": 1},
    )
    assert edition.edition_id == 1
    assert len(edition.sections) == 1
    assert len(edition.sections[0].entries) == 1
    assert edition.sections[0].entries[0].source_links == []
