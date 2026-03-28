"""Tests for query and export functions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.reporting.export import (
    claims_to_csv,
    claims_to_json,
    events_to_csv,
    events_to_json,
)
from ai_benchmark.reporting.query import (
    count_events_by_org,
    count_events_by_type,
    get_claims,
    get_events,
    get_recent_changes,
    get_unconfirmed_claims,
)


def _make_event(session, **kwargs) -> EventRecord:
    defaults = {
        "source_id": 1,
        "title": "Test Event",
        "normalized_title": "test event",
        "organization": "OpenAI",
        "source_type": "changelog",
        "canonical_path": "/test",
        "event_type": "model_release",
        "observed_at": datetime.now(timezone.utc),
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
        "observed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    claim = ClaimRecord(**defaults)
    session.add(claim)
    return claim


# ─── Query tests ───

@pytest.mark.asyncio
async def test_get_events_no_filter(db_session):
    _make_event(db_session, title="A", canonical_path="/a")
    _make_event(db_session, title="B", canonical_path="/b")
    await db_session.flush()

    events = await get_events(db_session)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_get_events_filter_by_org(db_session):
    _make_event(db_session, organization="OpenAI", canonical_path="/a")
    _make_event(db_session, organization="Anthropic", canonical_path="/b")
    await db_session.flush()

    events = await get_events(db_session, organization="OpenAI")
    assert len(events) == 1
    assert events[0].organization == "OpenAI"


@pytest.mark.asyncio
async def test_get_events_filter_by_model(db_session):
    _make_event(db_session, model_slug="gpt-5", canonical_path="/a")
    _make_event(db_session, model_slug="claude-4", canonical_path="/b")
    await db_session.flush()

    events = await get_events(db_session, model_slug="gpt-5")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_get_events_pagination(db_session):
    for i in range(10):
        _make_event(db_session, title=f"Event {i}", canonical_path=f"/{i}")
    await db_session.flush()

    page1 = await get_events(db_session, limit=3, offset=0)
    page2 = await get_events(db_session, limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 3
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_get_claims(db_session):
    event = _make_event(db_session)
    await db_session.flush()
    _make_claim(db_session, event.id, confirmation_status="confirmed")
    _make_claim(db_session, event.id, confirmation_status="unconfirmed")
    await db_session.flush()

    all_claims = await get_claims(db_session)
    assert len(all_claims) == 2

    unconfirmed = await get_unconfirmed_claims(db_session)
    assert len(unconfirmed) == 1


@pytest.mark.asyncio
async def test_get_recent_changes(db_session):
    now = datetime.now(timezone.utc)
    _make_event(db_session, observed_at=now, canonical_path="/recent")
    _make_event(
        db_session,
        observed_at=now - timedelta(hours=48),
        canonical_path="/old",
    )
    await db_session.flush()

    recent = await get_recent_changes(db_session, hours=24)
    assert len(recent) == 1


@pytest.mark.asyncio
async def test_count_events_by_org(db_session):
    _make_event(db_session, organization="OpenAI", canonical_path="/a")
    _make_event(db_session, organization="OpenAI", canonical_path="/b")
    _make_event(db_session, organization="Anthropic", canonical_path="/c")
    await db_session.flush()

    counts = await count_events_by_org(db_session)
    assert counts["OpenAI"] == 2
    assert counts["Anthropic"] == 1


@pytest.mark.asyncio
async def test_count_events_by_type(db_session):
    _make_event(db_session, event_type="model_release", canonical_path="/a")
    _make_event(db_session, event_type="pricing_change", canonical_path="/b")
    _make_event(db_session, event_type="model_release", canonical_path="/c")
    await db_session.flush()

    counts = await count_events_by_type(db_session)
    assert counts["model_release"] == 2
    assert counts["pricing_change"] == 1


# ─── Export tests ───

def test_events_to_json():
    event = EventRecord(
        id=1, source_id=1, title="GPT-5",
        normalized_title="gpt-5", organization="OpenAI",
        source_type="changelog", canonical_path="/test",
        event_type="model_release", model_slug="gpt-5",
        published_date="2026-03-28",
        observed_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    result = events_to_json([event])
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["title"] == "GPT-5"
    assert data[0]["model_slug"] == "gpt-5"


def test_events_to_csv():
    event = EventRecord(
        id=1, source_id=1, title="GPT-5",
        normalized_title="gpt-5", organization="OpenAI",
        source_type="changelog", canonical_path="/test",
        event_type="model_release",
        observed_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    result = events_to_csv([event])
    lines = result.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
    assert "GPT-5" in lines[1]


def test_claims_to_json():
    claim = ClaimRecord(
        id=1, event_id=1, claim_text="GPT-5 released",
        source_type="changelog", source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
        observed_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    result = claims_to_json([claim])
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["confidence_tier"] == "official_self_report"


def test_claims_to_csv():
    claim = ClaimRecord(
        id=1, event_id=1, claim_text="GPT-5 released",
        source_type="changelog", source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
        observed_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    result = claims_to_csv([claim])
    lines = result.strip().split("\n")
    assert len(lines) == 2
    assert "official_self_report" in lines[1]
