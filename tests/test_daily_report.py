"""Tests for the daily intelligence report queries and formatters."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, CrossReference, EventRecord
from ai_benchmark.reporting.report_formatter import format_json, format_markdown
from ai_benchmark.reporting.report_queries import (
    Article,
    ClaimDetail,
    CrossRefDetail,
    DailyReport,
    OrgActivity,
    WeeklyStats,
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
    now = datetime.now(UTC)
    article = Article(
        title="GPT-5 Launch",
        published_date="2026-04-01",
        publisher="OpenAI",
        source_type="changelog",
        event_type="model_release",
        model_slug="gpt-5",
        claims=[
            ClaimDetail(
                text="GPT-5 released with improved reasoning",
                source_name="OpenAI",
                confidence_tier="official_self_report",
                confirmation_status="confirmed",
            ),
            ClaimDetail(
                text="GPT-5 available via API",
                source_name="Reuters",
                confidence_tier="high_secondary",
                confirmation_status="confirmed",
            ),
        ],
        cross_refs=[
            CrossRefDetail(
                relationship_type="confirms",
                other_title="GPT-5 pricing update",
                other_org="OpenAI",
            )
        ],
        event_id=1,
    )
    pricing_article = Article(
        title="GPT-5 Pricing",
        published_date="2026-04-01",
        publisher="OpenAI",
        source_type="pricing_page",
        event_type="pricing_change",
        model_slug="gpt-5",
        event_id=2,
    )
    anthropic_article = Article(
        title="Claude Opus 4.6 Released",
        published_date="2026-03-30",
        publisher="Anthropic",
        source_type="newsroom",
        event_type="model_release",
        model_slug="claude-opus-4.6",
        event_id=3,
    )
    return DailyReport(
        generated_at=now,
        yesterday=[article, pricing_article],
        last_7_days=[article, pricing_article, anthropic_article],
        weekly_stats=WeeklyStats(
            total_events=10,
            total_unique_claims=25,
            by_org=[
                OrgActivity(organization="OpenAI", event_count=7, by_type={"model_release": 5}),
                OrgActivity(organization="Anthropic", event_count=3, by_type={"model_release": 3}),
            ],
            by_type={"model_release": 8, "pricing_change": 2},
            model_activity={"gpt-5": 5, "claude-opus-4.6": 3},
            confirmed_count=4,
            conflicted_count=1,
        ),
    )


# ─── Query tests ───


@pytest.mark.asyncio
async def test_gather_daily_report_empty(db_session):
    data = await gather_daily_report(db_session)
    assert data.yesterday == []
    assert data.last_7_days == []
    assert data.weekly_stats.total_events == 0


@pytest.mark.asyncio
async def test_gather_report_filters_by_published_date(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    old_date = "2024-01-15"

    _make_event(db_session, title="Recent Event", canonical_path="/a", published_date=today)
    _make_event(db_session, title="Old Event", canonical_path="/b", published_date=old_date)
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.last_7_days]
    assert "Recent Event" in titles
    assert "Old Event" not in titles


@pytest.mark.asyncio
async def test_gather_report_deduplicates_claims(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    event = _make_event(
        db_session, title="GPT-5 Launch", canonical_path="/launch", published_date=today
    )
    await db_session.flush()

    # Add same claim text multiple times (simulating multiple polls)
    for _ in range(5):
        _make_claim(db_session, event.id, claim_text="GPT-5 is here")
    # Add a different claim
    _make_claim(db_session, event.id, claim_text="GPT-5 available via API", source_name="Reuters")
    await db_session.flush()

    data = await gather_daily_report(db_session)
    article = next(a for a in data.yesterday if a.title == "GPT-5 Launch")
    # Should have 2 unique claims, not 6
    assert len(article.claims) == 2


@pytest.mark.asyncio
async def test_gather_report_includes_cross_refs(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    e1 = _make_event(
        db_session,
        title="OpenAI releases GPT-6",
        canonical_path="/a",
        published_date=today,
    )
    e2 = _make_event(
        db_session,
        title="Anthropic launches Claude 5",
        canonical_path="/b",
        published_date=today,
    )
    await db_session.flush()
    xref = CrossReference(
        record_a_id=e1.id,
        record_b_id=e2.id,
        relationship_type="confirms",
        created_at=datetime.now(UTC),
    )
    db_session.add(xref)
    await db_session.flush()

    data = await gather_daily_report(db_session)
    has_xref = any(len(a.cross_refs) > 0 for a in data.yesterday)
    assert has_xref


@pytest.mark.asyncio
async def test_gather_report_yesterday_subset_of_weekly(db_session):
    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    three_days_ago = (now - timedelta(days=3)).strftime("%Y-%m-%d")

    _make_event(db_session, title="Today Event", canonical_path="/a", published_date=today)
    _make_event(db_session, title="Older Event", canonical_path="/b", published_date=three_days_ago)
    await db_session.flush()

    data = await gather_daily_report(db_session)
    yesterday_titles = {a.title for a in data.yesterday}
    weekly_titles = {a.title for a in data.last_7_days}
    assert yesterday_titles <= weekly_titles


@pytest.mark.asyncio
async def test_gather_report_filters_short_titles(db_session):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    _make_event(db_session, title="OK Event Title", canonical_path="/a", published_date=today)
    _make_event(db_session, title="Hi", canonical_path="/b", published_date=today)
    await db_session.flush()

    data = await gather_daily_report(db_session)
    titles = [a.title for a in data.yesterday]
    assert "OK Event Title" in titles
    assert "Hi" not in titles


# ─── Formatter tests ───


def test_format_markdown_structure():
    data = _stub_report()
    md = format_markdown(data)
    assert "# AI Benchmark Daily Report" in md
    assert "# Yesterday" in md
    assert "# Last 7 Days" in md
    assert "# Weekly Summary" in md


def test_format_markdown_articles_grouped_by_publisher():
    data = _stub_report()
    md = format_markdown(data)
    assert "## OpenAI" in md
    assert "## Anthropic" in md


def test_format_markdown_article_has_metadata():
    data = _stub_report()
    md = format_markdown(data)
    assert "**Publisher:** OpenAI" in md
    assert "**Date:** 2026-04-01" in md
    assert "**Model:** `gpt-5`" in md
    assert "**Type:** Model Release" in md


def test_format_markdown_claims_displayed():
    data = _stub_report()
    md = format_markdown(data)
    assert "GPT-5 released with improved reasoning" in md
    assert "official self report" in md
    assert "GPT-5 available via API" in md
    assert "Reuters" in md


def test_format_markdown_cross_refs_displayed():
    data = _stub_report()
    md = format_markdown(data)
    assert "confirms" in md
    assert "GPT-5 pricing update" in md


def test_format_markdown_empty_report():
    now = datetime.now(UTC)
    data = DailyReport(
        generated_at=now,
        yesterday=[],
        last_7_days=[],
        weekly_stats=WeeklyStats(
            total_events=0,
            total_unique_claims=0,
            by_org=[],
            by_type={},
            model_activity={},
            confirmed_count=0,
            conflicted_count=0,
        ),
    )
    md = format_markdown(data)
    assert "No articles" in md


def test_format_markdown_weekly_stats():
    data = _stub_report()
    md = format_markdown(data)
    assert "| OpenAI |" in md
    assert "| `gpt-5` |" in md
    assert "**4** confirmed" in md


def test_format_json_roundtrip():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    assert "yesterday" in parsed
    assert "last_7_days" in parsed
    assert "weekly_stats" in parsed
    assert len(parsed["yesterday"]) == 2
    assert len(parsed["last_7_days"]) == 3


def test_format_json_datetime_serialization():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    assert "T" in parsed["generated_at"]
