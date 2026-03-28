"""Tests for cross-reference table builder."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai_benchmark.models.events import CrossReference, EventRecord
from ai_benchmark.processing.cross_reference import (
    build_cross_references,
    create_cross_reference,
    determine_relationship,
    find_related_by_model,
    find_related_by_org_event_type,
    xref_exists,
)


def _make_event(session, **kwargs) -> EventRecord:
    defaults = {
        "source_id": 1,
        "title": "Test Event",
        "normalized_title": "test event",
        "organization": "OpenAI",
        "source_type": "changelog",
        "canonical_path": "/changelog",
        "event_type": "model_release",
        "observed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    event = EventRecord(**defaults)
    session.add(event)
    return event


@pytest.mark.asyncio
async def test_find_related_by_model(db_session):
    event_a = _make_event(db_session, model_slug="gpt-5", title="GPT-5 on changelog")
    event_b = _make_event(
        db_session, model_slug="gpt-5", title="GPT-5 on newsroom",
        source_type="newsroom", canonical_path="/news/gpt5",
    )
    _make_event(db_session, model_slug="claude-4", title="Claude 4 released")
    await db_session.flush()

    related = await find_related_by_model(db_session, event_a)
    assert len(related) == 1
    assert related[0].id == event_b.id


@pytest.mark.asyncio
async def test_find_related_by_model_time_window(db_session):
    now = datetime.now(timezone.utc)
    event_a = _make_event(db_session, model_slug="gpt-5", observed_at=now)
    _make_event(
        db_session, model_slug="gpt-5",
        observed_at=now - timedelta(days=30),  # outside 7-day window
        canonical_path="/old",
    )
    await db_session.flush()

    related = await find_related_by_model(db_session, event_a, time_window_days=7)
    assert len(related) == 0


@pytest.mark.asyncio
async def test_find_related_by_org_event_type(db_session):
    event_a = _make_event(
        db_session, organization="OpenAI", event_type="model_release",
        title="GPT-5", canonical_path="/a",
    )
    event_b = _make_event(
        db_session, organization="OpenAI", event_type="model_release",
        title="GPT-5 API", canonical_path="/b",
    )
    _make_event(
        db_session, organization="Anthropic", event_type="model_release",
        title="Claude", canonical_path="/c",
    )
    await db_session.flush()

    related = await find_related_by_org_event_type(db_session, event_a)
    assert len(related) == 1
    assert related[0].id == event_b.id


def test_determine_relationship_confirms():
    event_a = EventRecord(
        source_id=1, title="A", normalized_title="a", organization="OpenAI",
        source_type="changelog", canonical_path="/a", event_type="model_release",
        model_slug="gpt-5", observed_at=datetime.now(timezone.utc),
    )
    event_b = EventRecord(
        source_id=1, title="B", normalized_title="b", organization="OpenAI",
        source_type="newsroom", canonical_path="/b", event_type="model_release",
        model_slug="gpt-5", observed_at=datetime.now(timezone.utc),
    )
    assert determine_relationship(event_a, event_b) == "confirms"


def test_determine_relationship_supplements_same_org():
    event_a = EventRecord(
        source_id=1, title="A", normalized_title="a", organization="OpenAI",
        source_type="changelog", canonical_path="/a", event_type="model_release",
        observed_at=datetime.now(timezone.utc),
    )
    event_b = EventRecord(
        source_id=1, title="B", normalized_title="b", organization="OpenAI",
        source_type="changelog", canonical_path="/b", event_type="model_release",
        observed_at=datetime.now(timezone.utc),
    )
    assert determine_relationship(event_a, event_b) == "supplements"


@pytest.mark.asyncio
async def test_create_cross_reference(db_session):
    event_a = _make_event(db_session, model_slug="gpt-5", source_type="changelog", canonical_path="/a")
    event_b = _make_event(db_session, model_slug="gpt-5", source_type="newsroom", canonical_path="/b")
    await db_session.flush()

    xref = await create_cross_reference(db_session, event_a, event_b)
    assert xref is not None
    assert xref.relationship_type == "confirms"
    assert xref.record_a_id == event_a.id
    assert xref.record_b_id == event_b.id


@pytest.mark.asyncio
async def test_no_duplicate_cross_references(db_session):
    event_a = _make_event(db_session, canonical_path="/a")
    event_b = _make_event(db_session, canonical_path="/b")
    await db_session.flush()

    xref1 = await create_cross_reference(db_session, event_a, event_b, "supplements")
    xref2 = await create_cross_reference(db_session, event_a, event_b, "supplements")
    assert xref1 is not None
    assert xref2 is None  # duplicate prevented


@pytest.mark.asyncio
async def test_no_duplicate_reverse_direction(db_session):
    event_a = _make_event(db_session, canonical_path="/a")
    event_b = _make_event(db_session, canonical_path="/b")
    await db_session.flush()

    xref1 = await create_cross_reference(db_session, event_a, event_b, "confirms")
    xref2 = await create_cross_reference(db_session, event_b, event_a, "confirms")
    assert xref1 is not None
    assert xref2 is None  # reverse direction also detected


@pytest.mark.asyncio
async def test_build_cross_references(db_session):
    event_a = _make_event(
        db_session, model_slug="gpt-5", source_type="changelog",
        title="GPT-5 changelog", canonical_path="/changelog",
    )
    event_b = _make_event(
        db_session, model_slug="gpt-5", source_type="newsroom",
        title="GPT-5 newsroom", canonical_path="/newsroom",
    )
    await db_session.flush()

    xrefs = await build_cross_references(db_session, event_a)
    assert len(xrefs) >= 1
    assert any(x.record_b_id == event_b.id for x in xrefs)
