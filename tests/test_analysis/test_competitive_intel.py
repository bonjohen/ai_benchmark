"""Tests for competitive intelligence service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.analysis.services.competitive_intel import (
    detect_competitive_clusters,
    get_activity_timeline,
    org_activity_summary,
)
from ai_benchmark.models.events import EventRecord
from ai_benchmark.models.sources import Page, Source


@pytest.fixture
async def multi_org_events(db_session):
    """Create events from multiple organizations for cluster detection."""
    now = datetime.now(UTC)

    # Create two sources
    openai_source = Source(
        source_name="OpenAI",
        category="official company source",
        organization="OpenAI",
        homepage_url="https://openai.com/",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="primary source",
        classification="primary",
        collection_method="html",
    )
    google_source = Source(
        source_name="Google",
        category="official company source",
        organization="Google",
        homepage_url="https://ai.google/",
        base_domain="google.com",
        trust_rating=5.0,
        source_role="primary source",
        classification="primary",
        collection_method="html",
    )
    db_session.add_all([openai_source, google_source])
    await db_session.flush()

    openai_page = Page(
        source_id=openai_source.id,
        canonical_url="https://openai.com/news/",
        page_type="product-news index",
        polling_frequency="daily",
    )
    google_page = Page(
        source_id=google_source.id,
        canonical_url="https://ai.google/discover/",
        page_type="product-news index",
        polling_frequency="daily",
    )
    db_session.add_all([openai_page, google_page])
    await db_session.flush()

    events = [
        # OpenAI model release — 2 days ago
        EventRecord(
            source_id=openai_source.id,
            page_id=openai_page.id,
            title="GPT-5 Released",
            normalized_title="gpt-5 released",
            organization="OpenAI",
            source_type="product-news index",
            canonical_path="https://openai.com/news/gpt-5",
            published_date="2026-03-27",
            event_type="model_release",
            model_slug="gpt-5",
            observed_at=now - timedelta(days=2),
        ),
        # Google model release — 1 day ago (same week = cluster)
        EventRecord(
            source_id=google_source.id,
            page_id=google_page.id,
            title="Gemini 3 Released",
            normalized_title="gemini 3 released",
            organization="Google",
            source_type="product-news index",
            canonical_path="https://ai.google/gemini-3",
            published_date="2026-03-28",
            event_type="model_release",
            model_slug="gemini-3",
            observed_at=now - timedelta(days=1),
        ),
        # OpenAI pricing change — 3 days ago
        EventRecord(
            source_id=openai_source.id,
            page_id=openai_page.id,
            title="GPT-5 Pricing",
            normalized_title="gpt-5 pricing",
            organization="OpenAI",
            source_type="pricing",
            canonical_path="https://openai.com/pricing",
            published_date="2026-03-26",
            event_type="pricing_change",
            model_slug="gpt-5",
            observed_at=now - timedelta(days=3),
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()
    return events


# --- get_activity_timeline ---


@pytest.mark.asyncio
async def test_get_activity_timeline(db_session, multi_org_events):
    """get_activity_timeline returns org summaries and clusters."""
    timeline = await get_activity_timeline(db_session, window_days=30)
    assert timeline.window_start is not None
    assert timeline.window_end is not None
    assert len(timeline.org_activities) == 2  # OpenAI and Google


@pytest.mark.asyncio
async def test_activity_timeline_org_counts(db_session, multi_org_events):
    """Org activities have correct event counts."""
    timeline = await get_activity_timeline(db_session, window_days=30)
    by_org = {o.organization: o for o in timeline.org_activities}

    assert by_org["OpenAI"].total_events == 2  # release + pricing
    assert by_org["Google"].total_events == 1  # release


@pytest.mark.asyncio
async def test_activity_timeline_active_models(db_session, multi_org_events):
    """Org activities track active model slugs."""
    timeline = await get_activity_timeline(db_session, window_days=30)
    by_org = {o.organization: o for o in timeline.org_activities}

    assert "gpt-5" in by_org["OpenAI"].active_models
    assert "gemini-3" in by_org["Google"].active_models


@pytest.mark.asyncio
async def test_activity_timeline_filter_org(db_session, multi_org_events):
    """Organization filter limits results."""
    timeline = await get_activity_timeline(db_session, window_days=30, organizations=["OpenAI"])
    assert len(timeline.org_activities) == 1
    assert timeline.org_activities[0].organization == "OpenAI"


@pytest.mark.asyncio
async def test_activity_timeline_narrow_window(db_session, multi_org_events):
    """Narrow window excludes older events."""
    timeline = await get_activity_timeline(db_session, window_days=1)
    # Only the Google event (1 day ago) should be included
    total = sum(o.total_events for o in timeline.org_activities)
    assert total <= 2  # at most the 1-day-ago events


# --- detect_competitive_clusters ---


@pytest.mark.asyncio
async def test_detect_clusters(db_session, multi_org_events):
    """Detects model_release cluster when 2+ orgs release in same week."""
    clusters = await detect_competitive_clusters(db_session, window_days=30)
    release_clusters = [c for c in clusters if c.event_type == "model_release"]
    assert len(release_clusters) == 1
    assert set(release_clusters[0].organizations) == {"OpenAI", "Google"}


@pytest.mark.asyncio
async def test_detect_clusters_min_orgs(db_session, multi_org_events):
    """min_orgs=3 means no clusters with only 2 orgs."""
    clusters = await detect_competitive_clusters(db_session, window_days=30, min_orgs=3)
    assert len(clusters) == 0


@pytest.mark.asyncio
async def test_detect_clusters_empty(db_session):
    """No events means no clusters."""
    clusters = await detect_competitive_clusters(db_session, window_days=30)
    assert clusters == []


# --- org_activity_summary ---


@pytest.mark.asyncio
async def test_org_activity_summary(db_session, multi_org_events):
    """org_activity_summary returns correct counts for a single org."""
    summary = await org_activity_summary(db_session, "OpenAI", window_days=30)
    assert summary.organization == "OpenAI"
    assert summary.total_events == 2
    assert "model_release" in summary.event_counts
    assert "pricing_change" in summary.event_counts
    assert "gpt-5" in summary.active_models


@pytest.mark.asyncio
async def test_org_activity_summary_unknown_org(db_session, multi_org_events):
    """Unknown org returns empty summary."""
    summary = await org_activity_summary(db_session, "Anthropic", window_days=30)
    assert summary.total_events == 0
    assert summary.active_models == []
