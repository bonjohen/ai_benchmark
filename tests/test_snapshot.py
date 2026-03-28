"""Tests for snapshot storage and comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_benchmark.collection.snapshot import SnapshotManager, compute_content_hash
from ai_benchmark.models.sources import Page, Source

FIXTURES = Path(__file__).parent / "fixtures"


def test_content_hash_deterministic():
    assert compute_content_hash("hello") == compute_content_hash("hello")
    assert compute_content_hash("hello") != compute_content_hash("world")


@pytest.mark.asyncio
async def test_store_and_retrieve_snapshot(db_session):
    source = Source(
        source_name="Test",
        category="test",
        organization="Test",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://example.com/changelog",
        page_type="changelog",
    )
    db_session.add(page)
    await db_session.flush()

    mgr = SnapshotManager(db_session)
    snapshot = await mgr.store_snapshot(page.id, "test content")
    assert snapshot.content_hash == compute_content_hash("test content")

    latest = await mgr.get_latest_snapshot(page.id)
    assert latest is not None
    assert latest.content == "test content"


@pytest.mark.asyncio
async def test_compare_detects_no_change(db_session):
    source = Source(
        source_name="Test2",
        category="test",
        organization="Test",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://example.com/pricing",
        page_type="pricing",
    )
    db_session.add(page)
    await db_session.flush()

    html = (FIXTURES / "pricing_v1.html").read_text()

    mgr = SnapshotManager(db_session)
    # First fetch — always "changed" (no previous)
    diff1, snap1 = await mgr.compare_with_latest(page.id, html)
    assert diff1.changed

    # Same content — no change
    diff2, snap2 = await mgr.compare_with_latest(page.id, html)
    assert not diff2.changed


@pytest.mark.asyncio
async def test_compare_detects_change(db_session):
    source = Source(
        source_name="Test3",
        category="test",
        organization="Test",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://example.com/changelog",
        page_type="changelog",
    )
    db_session.add(page)
    await db_session.flush()

    v1 = (FIXTURES / "changelog_v1.html").read_text()
    v2 = (FIXTURES / "changelog_v2.html").read_text()

    mgr = SnapshotManager(db_session)
    await mgr.compare_with_latest(page.id, v1)
    diff, snap = await mgr.compare_with_latest(page.id, v2)
    assert diff.changed
    assert any("gpt-5" in line for line in diff.added_lines)
