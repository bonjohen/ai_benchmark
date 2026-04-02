"""Tests for the daily intelligence report queries and formatters."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.models.events import ClaimRecord, CrossReference, EventRecord
from ai_benchmark.reporting.report_formatter import format_json, format_markdown
from ai_benchmark.reporting.report_queries import (
    ClaimSummary,
    CrossRefSummary,
    DailyReport,
    EventDetail,
    OrgActivity,
    RecentChangesReport,
    WeeklySummaryReport,
    gather_daily_report,
    gather_recent_changes,
    gather_weekly_summary,
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


def _make_xref(session, a_id: int, b_id: int, **kwargs) -> CrossReference:
    defaults = {
        "record_a_id": a_id,
        "record_b_id": b_id,
        "relationship_type": "supplements",
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    xref = CrossReference(**defaults)
    session.add(xref)
    return xref


def _stub_report() -> DailyReport:
    """Build a minimal DailyReport for formatter tests."""
    now = datetime.now(UTC)
    claims = [
        ClaimSummary(
            claim_text="GPT-5 released",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
            observed_at=now,
        ),
    ]
    event = EventDetail(
        event_id=1,
        title="GPT-5 Launch",
        organization="OpenAI",
        event_type="model_release",
        model_slug="gpt-5",
        published_date="2026-04-01",
        observed_at=now,
        source_type="changelog",
        claims=claims,
        cross_refs=[
            CrossRefSummary(
                relationship_type="confirms",
                other_event_title="GPT-5 pricing update",
                other_event_org="OpenAI",
            )
        ],
    )
    pricing_event = EventDetail(
        event_id=2,
        title="GPT-5 Pricing",
        organization="OpenAI",
        event_type="pricing_change",
        model_slug="gpt-5",
        published_date="2026-04-01",
        observed_at=now,
        source_type="pricing_page",
        claims=[],
        cross_refs=[],
    )
    recent = RecentChangesReport(
        generated_at=now,
        window_hours=24,
        events=[event, pricing_event],
        total_count=2,
    )
    weekly = WeeklySummaryReport(
        generated_at=now,
        window_days=7,
        total_events=10,
        total_claims=25,
        by_org=[OrgActivity(organization="OpenAI", event_count=10, by_type={"model_release": 5})],
        by_type={"model_release": 5, "announcement": 5},
        confirmed_events=[event],
        conflicted_events=[],
        model_activity={"gpt-5": 8, "claude-4": 3},
        notable_cross_refs=[
            CrossRefSummary(
                relationship_type="confirms",
                other_event_title="GPT-5 Launch (OpenAI) -> GPT-5 Pricing (OpenAI)",
                other_event_org="",
            )
        ],
    )
    return DailyReport(recent_changes=recent, weekly_summary=weekly)


# ─── Query tests ───


@pytest.mark.asyncio
async def test_gather_recent_changes_empty(db_session):
    data = await gather_recent_changes(db_session)
    assert data.total_count == 0
    assert data.events == []


@pytest.mark.asyncio
async def test_gather_recent_changes_with_claims(db_session):
    event = _make_event(db_session, title="GPT-5 Launch", canonical_path="/launch")
    await db_session.flush()
    _make_claim(db_session, event.id, claim_text="GPT-5 is here")
    _make_claim(db_session, event.id, claim_text="GPT-5 available now")
    await db_session.flush()

    data = await gather_recent_changes(db_session)
    assert data.total_count == 1
    assert len(data.events[0].claims) == 2


@pytest.mark.asyncio
async def test_gather_recent_changes_excludes_old(db_session):
    now = datetime.now(UTC)
    _make_event(db_session, observed_at=now, canonical_path="/recent")
    _make_event(
        db_session,
        observed_at=now - timedelta(hours=48),
        canonical_path="/old",
    )
    await db_session.flush()

    data = await gather_recent_changes(db_session, hours=24)
    assert data.total_count == 1


@pytest.mark.asyncio
async def test_gather_recent_changes_priority_ordering(db_session):
    now = datetime.now(UTC)
    _make_event(
        db_session,
        event_type="announcement",
        observed_at=now,
        canonical_path="/ann",
    )
    _make_event(
        db_session,
        event_type="model_release",
        observed_at=now - timedelta(minutes=5),
        canonical_path="/release",
    )
    await db_session.flush()

    data = await gather_recent_changes(db_session)
    assert data.events[0].event_type == "model_release"
    assert data.events[1].event_type == "announcement"


@pytest.mark.asyncio
async def test_gather_recent_changes_with_cross_refs(db_session):
    now = datetime.now(UTC)
    e1 = _make_event(db_session, title="Event A", canonical_path="/a", observed_at=now)
    e2 = _make_event(db_session, title="Event B", canonical_path="/b", observed_at=now)
    await db_session.flush()
    _make_xref(db_session, e1.id, e2.id, relationship_type="confirms")
    await db_session.flush()

    data = await gather_recent_changes(db_session)
    assert data.total_count == 2
    # At least one event should have a cross-ref
    has_xref = any(len(e.cross_refs) > 0 for e in data.events)
    assert has_xref


@pytest.mark.asyncio
async def test_gather_weekly_summary_aggregation(db_session):
    now = datetime.now(UTC)
    _make_event(db_session, organization="OpenAI", event_type="model_release", canonical_path="/a")
    _make_event(
        db_session, organization="Anthropic", event_type="announcement", canonical_path="/b"
    )
    _make_event(db_session, organization="OpenAI", event_type="pricing_change", canonical_path="/c")
    await db_session.flush()

    # Add claims for total count
    for i in range(5):
        _make_claim(db_session, event_id=1, claim_text=f"Claim {i}", observed_at=now)
    await db_session.flush()

    data = await gather_weekly_summary(db_session)
    assert data.total_events == 3
    assert data.total_claims == 5
    assert len(data.by_org) == 2
    assert data.by_type["model_release"] == 1
    assert data.by_type["announcement"] == 1
    assert data.by_type["pricing_change"] == 1


@pytest.mark.asyncio
async def test_gather_weekly_summary_confirmed_events(db_session):
    event = _make_event(db_session, title="Confirmed Event", canonical_path="/conf")
    await db_session.flush()
    _make_claim(db_session, event.id, confirmation_status="confirmed")
    await db_session.flush()

    data = await gather_weekly_summary(db_session)
    assert len(data.confirmed_events) == 1
    assert data.confirmed_events[0].title == "Confirmed Event"


@pytest.mark.asyncio
async def test_gather_weekly_summary_model_activity(db_session):
    e1 = _make_event(db_session, model_slug="gpt-5", canonical_path="/a")
    e2 = _make_event(db_session, model_slug="claude-4", canonical_path="/b")
    await db_session.flush()
    _make_claim(db_session, e1.id)
    _make_claim(db_session, e1.id, claim_text="Another claim")
    _make_claim(db_session, e2.id)
    await db_session.flush()

    data = await gather_weekly_summary(db_session)
    assert "gpt-5" in data.model_activity
    assert data.model_activity["gpt-5"] == 2


@pytest.mark.asyncio
async def test_gather_daily_report(db_session):
    _make_event(db_session, canonical_path="/test")
    await db_session.flush()

    data = await gather_daily_report(db_session)
    assert data.recent_changes.total_count == 1
    assert data.weekly_summary.total_events == 1


# ─── Formatter tests ───


def test_format_markdown_structure():
    data = _stub_report()
    md = format_markdown(data)
    assert "# AI Benchmark Daily Report" in md
    assert "## Recent Changes" in md
    assert "## 7-Day Summary" in md
    assert "### Model Releases" in md
    assert "### Pricing Changes" in md


def test_format_markdown_empty_sections_omitted():
    data = _stub_report()
    # Remove pricing event so that section is gone
    data.recent_changes.events = [
        e for e in data.recent_changes.events if e.event_type != "pricing_change"
    ]
    data.recent_changes.total_count = len(data.recent_changes.events)
    md = format_markdown(data)
    assert "### Pricing Changes" not in md


def test_format_markdown_claims_displayed():
    data = _stub_report()
    md = format_markdown(data)
    assert "GPT-5 released" in md
    assert "official self report" in md
    assert "confirmed" in md


def test_format_markdown_cross_refs_displayed():
    data = _stub_report()
    md = format_markdown(data)
    assert "confirms" in md
    assert "GPT-5 pricing update" in md


def test_format_markdown_empty_report():
    now = datetime.now(UTC)
    data = DailyReport(
        recent_changes=RecentChangesReport(
            generated_at=now, window_hours=24, events=[], total_count=0
        ),
        weekly_summary=WeeklySummaryReport(
            generated_at=now,
            window_days=7,
            total_events=0,
            total_claims=0,
            by_org=[],
            by_type={},
            confirmed_events=[],
            conflicted_events=[],
            model_activity={},
            notable_cross_refs=[],
        ),
    )
    md = format_markdown(data)
    assert "No new events detected" in md
    assert "No events recorded" in md


def test_format_json_roundtrip():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    assert "recent_changes" in parsed
    assert "weekly_summary" in parsed
    assert parsed["recent_changes"]["total_count"] == 2
    assert parsed["weekly_summary"]["total_events"] == 10


def test_format_json_datetime_serialization():
    data = _stub_report()
    result = format_json(data)
    parsed = json.loads(result)
    # Datetime should be an ISO string
    generated = parsed["recent_changes"]["generated_at"]
    assert "T" in generated  # ISO format
