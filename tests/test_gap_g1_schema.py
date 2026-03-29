"""Tests for Gap Phase G1: Schema extensions."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Snapshot, Source
from ai_benchmark.processing.deduplicator import find_exact_duplicate
from ai_benchmark.sources.base import RawItem
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _make_source(name: str = "TestSource") -> Source:
    return Source(
        source_name=name,
        category="test",
        organization="TestOrg",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=4.0,
        source_role="test",
        classification="primary",
    )


def _make_event(source_id: int, **overrides) -> EventRecord:
    defaults = dict(
        source_id=source_id,
        title="GPT-5 Released",
        normalized_title="gpt-5 released",
        organization="OpenAI",
        source_type="changelog",
        canonical_path="/news/gpt-5",
        published_date="2026-03-28",
        event_type="model_release",
        model_slug="gpt-5",
    )
    defaults.update(overrides)
    return EventRecord(**defaults)


@pytest.mark.asyncio
async def test_event_benchmark_variant_roundtrip(db_session: AsyncSession):
    """EventRecord stores and retrieves benchmark_variant and evaluation_conditions."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event = _make_event(
        source.id,
        benchmark_variant="verified",
        evaluation_conditions="SWE-bench Verified; contamination risk noted",
    )
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(EventRecord))
    e = result.scalar_one()
    assert e.benchmark_variant == "verified"
    assert e.evaluation_conditions == "SWE-bench Verified; contamination risk noted"


@pytest.mark.asyncio
async def test_event_benchmark_variant_nullable(db_session: AsyncSession):
    """benchmark_variant and evaluation_conditions default to None."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event = _make_event(source.id)
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(EventRecord))
    e = result.scalar_one()
    assert e.benchmark_variant is None
    assert e.evaluation_conditions is None


@pytest.mark.asyncio
async def test_claim_snapshot_id_roundtrip(db_session: AsyncSession):
    """ClaimRecord stores snapshot_id and it can be None."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://example.com/pricing",
        page_type="pricing",
    )
    db_session.add(page)
    await db_session.flush()

    snap = Snapshot(page_id=page.id, content_hash="abc123", content="<html>test</html>")
    db_session.add(snap)
    await db_session.flush()

    claim = ClaimRecord(
        claim_text="GPT-5 costs $5",
        source_type="pricing",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        snapshot_id=snap.id,
    )
    db_session.add(claim)
    await db_session.commit()

    result = await db_session.execute(select(ClaimRecord))
    c = result.scalar_one()
    assert c.snapshot_id == snap.id


@pytest.mark.asyncio
async def test_claim_snapshot_id_nullable(db_session: AsyncSession):
    """ClaimRecord.snapshot_id defaults to None."""
    claim = ClaimRecord(
        claim_text="Test claim",
        source_type="test",
        source_name="Test",
        confidence_tier="low_discovery",
    )
    db_session.add(claim)
    await db_session.commit()

    result = await db_session.execute(select(ClaimRecord))
    c = result.scalar_one()
    assert c.snapshot_id is None


@pytest.mark.asyncio
async def test_composite_key_allows_different_model_slugs(db_session: AsyncSession):
    """Same title but different model_slug should not be a duplicate."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event1 = _make_event(source.id, model_slug="gpt-5")
    event2 = _make_event(source.id, model_slug="gpt-5-turbo")
    db_session.add(event1)
    await db_session.flush()
    db_session.add(event2)
    await db_session.commit()

    result = await db_session.execute(select(EventRecord))
    assert len(result.scalars().all()) == 2


@pytest.mark.asyncio
async def test_composite_key_rejects_full_duplicate(db_session: AsyncSession):
    """True duplicate including model_slug should be rejected."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event1 = _make_event(source.id)
    db_session.add(event1)
    await db_session.flush()

    event2 = _make_event(source.id)
    db_session.add(event2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_find_exact_duplicate_with_model_slug(db_session: AsyncSession):
    """find_exact_duplicate matches when model_slug is provided."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event = _make_event(source.id)
    db_session.add(event)
    await db_session.flush()

    found = await find_exact_duplicate(
        db_session,
        "gpt-5 released",
        "OpenAI",
        "changelog",
        "/news/gpt-5",
        "2026-03-28",
        model_slug="gpt-5",
    )
    assert found is not None
    assert found.id == event.id


@pytest.mark.asyncio
async def test_find_exact_duplicate_no_match_different_slug(db_session: AsyncSession):
    """find_exact_duplicate returns None when model_slug differs."""
    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    event = _make_event(source.id, model_slug="gpt-5")
    db_session.add(event)
    await db_session.flush()

    found = await find_exact_duplicate(
        db_session,
        "gpt-5 released",
        "OpenAI",
        "changelog",
        "/news/gpt-5",
        "2026-03-28",
        model_slug="gpt-5-turbo",
    )
    assert found is None


@pytest.mark.asyncio
async def test_pipeline_populates_benchmark_variant(db_session: AsyncSession):
    """process_item sets benchmark_variant from RawItem metadata."""
    from ai_benchmark.processing.pipeline import process_item

    source = _make_source()
    db_session.add(source)
    await db_session.flush()

    item = RawItem(
        title="SWE-bench: GPT-5 = 72.3%",
        item_type="benchmark_entry",
        model_hint="gpt-5",
        metadata={
            "benchmark_variant": "verified",
            "evaluation_conditions": "SWE-bench Verified; bash-only",
        },
    )
    event = await process_item(
        db_session,
        item,
        source.id,
        None,
        "SWE-bench",
        "leaderboard",
        "secondary",
    )
    assert event is not None
    assert event.benchmark_variant == "verified"
    assert event.evaluation_conditions == "SWE-bench Verified; bash-only"
