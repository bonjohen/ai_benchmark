"""Tests for event record persistence."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ai_benchmark.models.events import EventRecord
from ai_benchmark.models.sources import Source
from ai_benchmark.sources.base import RawItem
from ai_benchmark.sources.persistence import persist_events


@pytest.mark.asyncio
async def test_persist_creates_event(db_session):
    source = Source(
        source_name="TestSource",
        category="test",
        organization="OpenAI",
        homepage_url="https://openai.com",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    items = [
        RawItem(
            title="Released GPT-5 with 1M context",
            url="/news/gpt-5",
            body="2026-03-28 — Released GPT-5 with 1M context window.",
            item_type="changelog_entry",
        )
    ]

    created = await persist_events(
        db_session, items, source.id, None, "OpenAI", "official company source"
    )
    assert len(created) == 1
    assert created[0].model_slug == "gpt-5"
    assert created[0].event_type == "model_release"
    assert created[0].published_date == "2026-03-28"


@pytest.mark.asyncio
async def test_persist_skips_duplicates(db_session):
    source = Source(
        source_name="TestSource2",
        category="test",
        organization="Anthropic",
        homepage_url="https://anthropic.com",
        base_domain="anthropic.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    items = [
        RawItem(title="Claude 4 Released", url="/news/claude-4", body="Introducing Claude 4")
    ]

    first = await persist_events(
        db_session, items, source.id, None, "Anthropic", "official company source"
    )
    assert len(first) == 1

    second = await persist_events(
        db_session, items, source.id, None, "Anthropic", "official company source"
    )
    assert len(second) == 0

    result = await db_session.execute(select(EventRecord))
    all_events = result.scalars().all()
    assert len(all_events) == 1
