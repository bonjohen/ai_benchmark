"""Tests for the post-collection processing pipeline."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ai_benchmark.models.events import ClaimRecord, CrossReference
from ai_benchmark.processing.pipeline import process_item, process_items
from ai_benchmark.sources.base import RawItem


@pytest.mark.asyncio
async def test_process_item_creates_event_and_claim(db_session):
    item = RawItem(
        title="OpenAI Releases GPT-5",
        url="/news/gpt5",
        body="OpenAI released GPT-5 with 1M context window",
        item_type="model_release",
    )

    event = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="newsroom",
        classification="primary",
    )
    assert event is not None
    assert event.normalized_title == "openai releases gpt-5"
    assert event.model_slug == "gpt-5"

    # Check claim was created
    result = await db_session.execute(select(ClaimRecord).where(ClaimRecord.event_id == event.id))
    claims = list(result.scalars().all())
    assert len(claims) == 1
    assert claims[0].confidence_tier == "official_self_report"


@pytest.mark.asyncio
async def test_process_item_skips_duplicate(db_session):
    item = RawItem(
        title="OpenAI Releases GPT-5",
        url="/news/gpt5",
        body="OpenAI released GPT-5",
        item_type="model_release",
    )

    event1 = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="newsroom",
        classification="primary",
    )
    assert event1 is not None

    # Same item again — should be deduplicated
    event2 = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="newsroom",
        classification="primary",
    )
    assert event2 is None


@pytest.mark.asyncio
async def test_process_duplicate_adds_claim_to_existing(db_session):
    item = RawItem(
        title="OpenAI Releases GPT-5",
        url="/news/gpt5",
        body="OpenAI released GPT-5",
        item_type="model_release",
    )

    event = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="newsroom",
        classification="primary",
    )

    # Same event from a different source
    dup_item = RawItem(
        title="OpenAI Releases GPT-5",
        url="/changelog/gpt5",
        body="GPT-5 now available in the API",
        item_type="model_release",
    )
    result = await process_item(
        db_session,
        dup_item,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="changelog",
        classification="primary",
    )
    assert result is None  # Duplicate

    # But a claim should have been added to the existing event
    claims_result = await db_session.execute(
        select(ClaimRecord).where(ClaimRecord.event_id == event.id)
    )
    claims = list(claims_result.scalars().all())
    assert len(claims) == 2


@pytest.mark.asyncio
async def test_process_item_builds_cross_references(db_session):
    """Cross-references link events across different organizations reporting on the same model."""
    item_a = RawItem(
        title="OpenAI Releases GPT-5 Model",
        url="/news/gpt5",
        body="Released GPT-5",
        item_type="model_release",
        model_hint="gpt-5",
    )
    event_a = await process_item(
        db_session,
        item_a,
        source_id=1,
        page_id=None,
        organization="OpenAI",
        source_type="newsroom",
        classification="primary",
    )
    assert event_a is not None

    # Different organization reporting on same model — not a duplicate
    item_b = RawItem(
        title="Reuters Reports GPT-5 Launch",
        url="/reuters/gpt5",
        body="GPT-5 launched by OpenAI",
        item_type="news_article",
        model_hint="gpt-5",
    )
    event_b = await process_item(
        db_session,
        item_b,
        source_id=2,
        page_id=None,
        organization="Reuters",
        source_type="news",
        classification="secondary",
    )
    assert event_b is not None

    # Check cross-reference was created
    result = await db_session.execute(select(CrossReference))
    xrefs = list(result.scalars().all())
    assert len(xrefs) >= 1


@pytest.mark.asyncio
async def test_process_items_batch(db_session):
    items = [
        RawItem(
            title="Anthropic Launches Claude 4 Opus",
            url="/a",
            body="Claude 4 Opus",
            item_type="model_release",
        ),
        RawItem(
            title="Google Announces Gemini 3.0 Ultra",
            url="/b",
            body="Gemini 3.0 Ultra",
            item_type="model_release",
        ),
        RawItem(
            title="API Token Pricing Updated for Q2 2026",
            url="/pricing",
            body="New pricing structure",
            item_type="pricing_change",
        ),
    ]

    created = await process_items(
        db_session,
        items,
        source_id=1,
        page_id=None,
        organization="TestOrg",
        source_type="newsroom",
        classification="secondary",
    )
    assert len(created) == 3


@pytest.mark.asyncio
async def test_process_item_discovery_classification(db_session):
    item = RawItem(
        title="Forum Discussion About New Model",
        url="/forum/thread/123",
        body="People are discussing a new model",
        item_type="forum_topic",
    )

    event = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="Community",
        source_type="forum",
        classification="discovery-only",
    )

    result = await db_session.execute(select(ClaimRecord).where(ClaimRecord.event_id == event.id))
    claims = list(result.scalars().all())
    assert claims[0].confidence_tier == "low_discovery"


@pytest.mark.asyncio
async def test_process_items_batch_dedup_still_works(db_session):
    """Batch dedup optimization doesn't break dedup — duplicates produce claims, not new events."""
    item = RawItem(
        title="Anthropic Launches Claude 4 Opus",
        url="/a",
        body="Claude 4 Opus released",
        item_type="model_release",
    )
    # First pass creates the event
    created = await process_items(
        db_session,
        [item],
        source_id=1,
        page_id=None,
        organization="Anthropic",
        source_type="newsroom",
        classification="primary",
    )
    assert len(created) == 1

    # Second pass with same item — should be deduplicated
    dup_item = RawItem(
        title="Anthropic Launches Claude 4 Opus",
        url="/b",
        body="Claude 4 Opus is here",
        item_type="model_release",
    )
    created2 = await process_items(
        db_session,
        [dup_item],
        source_id=1,
        page_id=None,
        organization="Anthropic",
        source_type="changelog",
        classification="primary",
    )
    assert len(created2) == 0

    # But a claim was added to the original event
    result = await db_session.execute(
        select(ClaimRecord).where(ClaimRecord.event_id == created[0].id)
    )
    claims = list(result.scalars().all())
    assert len(claims) == 2


# ─── Logging tests ───


@pytest.mark.asyncio
async def test_process_item_logs_event_created(db_session, capture_logs):
    item = RawItem(
        title="Anthropic Ships Claude 5",
        url="/blog/claude5",
        body="Anthropic released Claude 5 with improved reasoning.",
        item_type="model_release",
    )
    event = await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="Anthropic",
        source_type="newsroom",
        classification="primary",
    )
    assert event is not None

    event_names = [entry["event"] for entry in capture_logs]
    assert "event_created" in event_names


@pytest.mark.asyncio
async def test_process_item_logs_duplicate(db_session, capture_logs):
    item = RawItem(
        title="Anthropic Ships Claude 5",
        url="/blog/claude5",
        body="Anthropic released Claude 5.",
        item_type="model_release",
    )
    await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="Anthropic",
        source_type="newsroom",
        classification="primary",
    )
    # Second time — duplicate
    await process_item(
        db_session,
        item,
        source_id=1,
        page_id=None,
        organization="Anthropic",
        source_type="newsroom",
        classification="primary",
    )
    event_names = [entry["event"] for entry in capture_logs]
    assert "item_duplicate" in event_names
