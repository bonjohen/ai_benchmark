"""Tests for composite-key deduplication and fuzzy matching."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_benchmark.models.events import EventRecord
from ai_benchmark.processing.deduplicator import (
    find_exact_duplicate,
    find_model_duplicate,
    find_near_duplicates,
    is_duplicate,
    is_near_duplicate,
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
        "observed_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    event = EventRecord(**defaults)
    session.add(event)
    return event


@pytest.mark.asyncio
async def test_exact_duplicate_found(db_session):
    _make_event(db_session, normalized_title="gpt-5 released", canonical_path="/news/gpt5")
    await db_session.flush()

    result = await find_exact_duplicate(
        db_session, "gpt-5 released", "OpenAI", "changelog", "/news/gpt5", None
    )
    assert result is not None


@pytest.mark.asyncio
async def test_exact_duplicate_not_found(db_session):
    _make_event(db_session, normalized_title="gpt-5 released", canonical_path="/news/gpt5")
    await db_session.flush()

    result = await find_exact_duplicate(
        db_session, "gpt-6 released", "OpenAI", "changelog", "/news/gpt6", None
    )
    assert result is None


@pytest.mark.asyncio
async def test_model_duplicate_found(db_session):
    _make_event(
        db_session,
        normalized_title="gpt-5 released",
        model_slug="gpt-5",
        published_date="2026-03-28",
    )
    await db_session.flush()

    result = await find_model_duplicate(db_session, "gpt-5", "OpenAI", "2026-03-28")
    assert result is not None


@pytest.mark.asyncio
async def test_model_duplicate_different_date(db_session):
    _make_event(
        db_session,
        normalized_title="gpt-5 released",
        model_slug="gpt-5",
        published_date="2026-03-28",
    )
    await db_session.flush()

    result = await find_model_duplicate(db_session, "gpt-5", "OpenAI", "2026-04-01")
    assert result is None


def test_fuzzy_match_similar():
    assert is_near_duplicate("gpt-5 released today", "gpt-5 released today!", 0.85)


def test_fuzzy_match_different():
    assert not is_near_duplicate("gpt-5 released", "claude 4 launched", 0.85)


@pytest.mark.asyncio
async def test_near_duplicates_found(db_session):
    _make_event(
        db_session,
        normalized_title="openai releases gpt-5 with advanced reasoning",
    )
    await db_session.flush()

    results = await find_near_duplicates(
        db_session, "openai releases gpt-5 with advanced reasoning capabilities", "OpenAI"
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_is_duplicate_composite_key(db_session):
    _make_event(
        db_session,
        normalized_title="pricing update",
        canonical_path="/pricing",
        model_slug=None,
    )
    await db_session.flush()

    result = await is_duplicate(
        db_session, "pricing update", "OpenAI", "changelog", "/pricing", None, None
    )
    assert result is not None


@pytest.mark.asyncio
async def test_is_duplicate_returns_none_for_new(db_session):
    result = await is_duplicate(
        db_session, "brand new event", "NewOrg", "blog", "/blog/new", None, None
    )
    assert result is None
