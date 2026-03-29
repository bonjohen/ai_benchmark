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
    """execute_follow_up_tasks marks tasks as completed."""
    await enqueue_follow_up(db_session, "gpt-5", "OpenAI")
    completed = await execute_follow_up_tasks(db_session)
    assert completed == 4

    result = await db_session.execute(select(FollowUpTask))
    tasks = result.scalars().all()
    assert all(t.status == "completed" for t in tasks)
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
