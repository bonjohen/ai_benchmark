"""Tests for the model slug discovery queue."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ai_benchmark.models.discovery import FollowUpTask
from ai_benchmark.models.events import EventRecord
from ai_benchmark.models.sources import Source
from ai_benchmark.processing.discovery_queue import (
    DiscoveryQueue,
    enqueue_follow_up,
    execute_follow_up_tasks,
)


def _make_source(session, name="TestSource") -> Source:
    source = Source(
        source_name=name,
        category="test",
        organization="TestOrg",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=4.0,
        source_role="test",
        classification="primary",
    )
    session.add(source)
    return source


@pytest.mark.asyncio
async def test_check_new_slug_first_occurrence(db_session):
    """check_new_slug returns True for first occurrence."""
    queue = DiscoveryQueue()
    assert await queue.check_new_slug(db_session, "gpt-5") is True


@pytest.mark.asyncio
async def test_check_new_slug_repeat(db_session):
    """check_new_slug returns False for repeated slug."""
    queue = DiscoveryQueue()
    await queue.check_new_slug(db_session, "gpt-5")
    assert await queue.check_new_slug(db_session, "gpt-5") is False


@pytest.mark.asyncio
async def test_check_new_slug_loads_from_db(db_session):
    """check_new_slug loads existing slugs from DB on init."""
    source = _make_source(db_session)
    await db_session.flush()

    event = EventRecord(
        source_id=source.id,
        title="GPT-5",
        normalized_title="gpt-5",
        organization="OpenAI",
        source_type="changelog",
        canonical_path="/news",
        event_type="model_release",
        model_slug="gpt-5",
    )
    db_session.add(event)
    await db_session.flush()

    queue = DiscoveryQueue()
    assert await queue.check_new_slug(db_session, "gpt-5") is False
    assert await queue.check_new_slug(db_session, "claude-4") is True


@pytest.mark.asyncio
async def test_enqueue_follow_up_creates_tasks(db_session):
    """enqueue_follow_up creates 4 task records."""
    tasks = await enqueue_follow_up(db_session, "gpt-5", "OpenAI")
    assert len(tasks) == 4
    types = {t.task_type for t in tasks}
    assert types == {
        "pricing_search",
        "release_notes_search",
        "system_card_search",
        "benchmark_coverage_search",
    }
    assert all(t.model_slug == "gpt-5" for t in tasks)
    assert all(t.status == "pending" for t in tasks)


@pytest.mark.asyncio
async def test_execute_follow_up_tasks_marks_completed(db_session):
    """execute_follow_up_tasks marks tasks completed or failed (never pending)."""
    from unittest.mock import AsyncMock, MagicMock

    from ai_benchmark.collection.fetcher import FetchResult

    # Create the matching source and page in DB so source lookup succeeds
    source = Source(
        source_name="OpenAI",
        category="official company source",
        organization="OpenAI",
        homepage_url="https://openai.com/news/",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="primary",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    from ai_benchmark.models.sources import Page

    page = Page(
        source_id=source.id,
        canonical_url="https://openai.com/api/pricing/",
        page_type="pricing",
        polling_frequency="daily",
        priority=True,
    )
    db_session.add(page)
    await db_session.flush()

    # Mock fetcher returns successful empty HTML
    mock_fetcher = MagicMock()
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://openai.com/api/pricing/",
            status_code=200,
            body_text="<html></html>",
        )
    )

    await enqueue_follow_up(db_session, "gpt-5", "OpenAI")
    completed = await execute_follow_up_tasks(db_session, mock_fetcher)
    # At minimum, pricing_search should dispatch and complete (others may fail if no page match)
    assert completed >= 1

    result = await db_session.execute(select(FollowUpTask))
    tasks = result.scalars().all()
    assert all(t.status in ("completed", "failed") for t in tasks)
    assert all(t.completed_at is not None for t in tasks)


@pytest.mark.asyncio
async def test_process_item_creates_follow_ups(db_session):
    """Integration: process_item with new model slug creates follow-up tasks."""
    from ai_benchmark.processing import discovery_queue as dq_mod
    from ai_benchmark.processing.pipeline import process_item
    from ai_benchmark.sources.base import RawItem

    # Reset the module-level singleton to avoid stale state from other tests
    dq_mod._discovery_queue = dq_mod.DiscoveryQueue()

    source = _make_source(db_session)
    await db_session.flush()

    item = RawItem(
        title="GPT-6 Released",
        item_type="news_post",
        model_hint="gpt-6",
        body="OpenAI releases GPT-6 on 2026-03-28",
    )

    event = await process_item(
        db_session,
        item,
        source.id,
        None,
        "OpenAI",
        "changelog",
        "primary",
    )
    assert event is not None

    result = await db_session.execute(
        select(FollowUpTask).where(FollowUpTask.model_slug == "gpt-6")
    )
    tasks = result.scalars().all()
    assert len(tasks) == 4
