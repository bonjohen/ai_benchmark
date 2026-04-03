"""Tests for the daily intelligence report queries and formatters."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.reporting.report_formatter import format_json
from ai_benchmark.reporting.report_queries import (
    Article,
    DailyReport,
    _is_noise,
    gather_daily_report,
)

# ─── Helpers ───


def _make_event(session, **kwargs) -> EventRecord:
    defaults = {
        "source_id": 1,
        "title": "Test Event",
        "normalized_title": "test event",
        "organization": "OpenAI",
        "source_type": "changelog",
        "canonical_path": "/test",
        "event_type": "model_release",
        "observed_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    event = EventRecord(**defaults)
    session.add(event)
    return event


def _make_claim(session, event_id: int, **kwargs) -> ClaimRecord:
    defaults = {
        "event_id": event_id,
        "claim_text": "Test claim",
        "source_type": "changelog",
        "source_name": "OpenAI",
        "confidence_tier": "official_self_report",
        "confirmation_status": "unconfirmed",
        "observed_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    claim = ClaimRecord(**defaults)
    session.add(claim)
    return claim


def _stub_report() -> DailyReport:
    """Build a minimal DailyReport for formatter tests."""
    return DailyReport(
        generated_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC),
        articles=[
            Article(
                title="GPT-5 Launch",
                publisher="OpenAI",
                date="2026-04-01",
                model="gpt-5",
                abstract="OpenAI releases GPT-5 with improved reasoning capabilities.",
                url="https://openai.com/blog/gpt-5",
                confirmed=True,
                sources=2,
            ),
            Article(
                title="GPT-5 Pricing Update",
                publisher="OpenAI",
                date="2026-04-01",
                model="gpt-5",
                abstract="Input: $5/1M tokens, Output: $15/1M tokens.",
                url="https://openai.com/pricing",
                confirmed=False,
                sources=1,
            ),
        ],
    )


# ─── Noise filtering tests ───


class TestIsNoise:
    def test_short_title_is_noise(self):
        event = EventRecord(
            source_id=1,
            title="Hi",
            normalized_title="hi",
            organization="OpenAI",
            source_type="changelog",
            canonical_path="/test",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content="Some content here that is long enough to be valid.",
        )
        assert _is_noise(event) is True

    def test_empty_abstract_is_noise(self):
        event = EventRecord(
            source_id=1,
            title="Some Valid Title",
            normalized_title="some valid title",
            organization="OpenAI",
            source_type="changelog",
            canonical_path="/test",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content=None,
        )
        assert _is_noise(event) is True

    def test_abstract_equals_title_is_noise(self):
        event = EventRecord(
            source_id=1,
            title="Some Valid Title",
            normalized_title="some valid title",
            organization="OpenAI",
            source_type="changelog",
            canonical_path="/test",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content="Some Valid Title",
        )
        assert _is_noise(event) is True

    def test_non_ai_github_repo_is_noise(self):
        event = EventRecord(
            source_id=1,
            title="google/filament: v1.50.0",
            normalized_title="google/filament: v1.50.0",
            organization="Google",
            source_type="github_release",
            canonical_path="https://github.com/google/filament",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content="Updated rendering pipeline with new material system and bug fixes.",
        )
        assert _is_noise(event) is True

    def test_ai_github_repo_is_not_noise(self):
        event = EventRecord(
            source_id=1,
            title="openai/codex: v2.0.0",
            normalized_title="openai/codex: v2.0.0",
            organization="OpenAI",
            source_type="github_release",
            canonical_path="https://github.com/openai/codex",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content="Added batch processing and improved memory management for large contexts.",
        )
        assert _is_noise(event) is False

    def test_valid_non_github_event_is_not_noise(self):
        event = EventRecord(
            source_id=1,
            title="GPT-5 Launch Announcement",
            normalized_title="gpt-5 launch announcement",
            organization="OpenAI",
            source_type="changelog",
            canonical_path="https://openai.com/blog/gpt-5",
            event_type="model_release",
            observed_at=datetime.now(UTC),
            raw_content="OpenAI releases GPT-5 with improved reasoning and a new context window.",
        )
        assert _is_noise(event) is False


# ─── Query tests ───


@pytest.mark.asyncio
async def test_gather_daily_report_empty(db_session):
    data = await gather_daily_report(db_session)
    assert data.articles == []


@pytest.mark.asyncio
async def test_gather_report_filters_by_published_date(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    old_date = "2024-01-15"

    _make_event(
        db_session,
        title="Recent Event Title Here",
        canonical_path="/a",
        published_date=today,
        raw_content="This is a detailed description of the recent event with enough content.",
    )
    _make_event(
        db_session,
        title="Old Event Title Here",
        canonical_path="/b",
        published_date=old_date,
        raw_content="This is a detailed description of the old event with enough content.",
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.articles]
    assert "Recent Event Title Here" in titles
    assert "Old Event Title Here" not in titles


@pytest.mark.asyncio
async def test_gather_report_extracts_abstract(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    raw = (
        "## What's Changed\n\nAdded new feature for batch processing. Fixed memory leak in parser."
    )
    _make_event(
        db_session,
        title="openai/codex: v2.0",
        canonical_path="https://github.com/openai/codex",
        published_date=today,
        raw_content=raw,
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    article = data.articles[0]
    assert "batch processing" in article.abstract
    assert article.url == "https://github.com/openai/codex"


@pytest.mark.asyncio
async def test_gather_report_derives_confirmed(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    event = _make_event(
        db_session,
        title="GPT-5 Launch Event",
        canonical_path="/launch",
        published_date=today,
        raw_content="OpenAI releases GPT-5 with significantly improved capabilities.",
    )
    await db_session.flush()
    _make_claim(db_session, event.id, confidence_tier="high_secondary", source_name="Reuters")
    _make_claim(
        db_session,
        event.id,
        confidence_tier="official_self_report",
        source_name="OpenAI",
        confirmation_status="confirmed",
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    article = next(a for a in data.articles if a.title == "GPT-5 Launch Event")
    assert article.confirmed is True
    assert article.sources == 2


@pytest.mark.asyncio
async def test_gather_report_filters_short_titles(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    _make_event(
        db_session,
        title="OK Event Title Here",
        canonical_path="/a",
        published_date=today,
        raw_content="Detailed description with enough content to pass the filter.",
    )
    _make_event(
        db_session,
        title="Hi",
        canonical_path="/b",
        published_date=today,
        raw_content="Some content here.",
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.articles]
    assert "OK Event Title Here" in titles
    assert "Hi" not in titles


@pytest.mark.asyncio
async def test_gather_report_filters_no_abstract(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    _make_event(
        db_session,
        title="Event With Content",
        canonical_path="/a",
        published_date=today,
        raw_content="This event has real content to display in the report summary.",
    )
    _make_event(
        db_session,
        title="Event Without Content",
        canonical_path="/b",
        published_date=today,
        raw_content=None,
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.articles]
    assert "Event With Content" in titles
    assert "Event Without Content" not in titles


@pytest.mark.asyncio
async def test_gather_report_filters_non_ai_github(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    _make_event(
        db_session,
        title="google/filament: v1.50.0",
        canonical_path="https://github.com/google/filament",
        published_date=today,
        raw_content="Updated rendering engine with new materials and improved performance.",
    )
    _make_event(
        db_session,
        title="openai/codex: v2.0.0",
        canonical_path="https://github.com/openai/codex",
        published_date=today,
        raw_content="Added batch processing and improved memory management for contexts.",
    )
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.articles]
    assert "openai/codex: v2.0.0" in titles
    assert "google/filament: v1.50.0" not in titles


# ─── Formatter tests ───


def test_format_json_compact_structure():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    assert parsed["date"] == "2026-04-02"
    assert parsed["article_count"] == 2
    assert len(parsed["articles"]) == 2


def test_format_json_article_fields():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    article = parsed["articles"][0]
    expected_keys = {
        "title",
        "publisher",
        "date",
        "model",
        "abstract",
        "url",
        "confirmed",
        "sources",
    }
    assert set(article.keys()) == expected_keys
    assert article["title"] == "GPT-5 Launch"
    assert article["confirmed"] is True
    assert article["sources"] == 2


def test_format_json_no_legacy_fields():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    assert "yesterday" not in parsed
    assert "last_7_days" not in parsed
    assert "weekly_stats" not in parsed
    assert "generated_at" not in parsed
    article = parsed["articles"][0]
    assert "event_type" not in article
    assert "source_type" not in article
    assert "cross_refs" not in article
    assert "event_id" not in article
    assert "confidence_tier" not in article
    assert "confirmation_status" not in article
