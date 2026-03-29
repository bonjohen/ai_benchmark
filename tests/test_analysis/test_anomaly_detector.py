"""Tests for anomaly detector service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_benchmark.analysis.services.anomaly_detector import (
    detect_anomalies,
    get_recent_insights,
)
from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source


@pytest.fixture
async def anomaly_events(db_session):
    """Create events designed to trigger specific anomaly rules."""
    now = datetime.now(UTC)

    source = Source(
        source_name="TestSource",
        category="official company source",
        organization="TestOrg",
        homepage_url="https://test.org/",
        base_domain="test.org",
        trust_rating=5.0,
        source_role="primary source",
        classification="primary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://test.org/news/",
        page_type="product-news index",
        polling_frequency="daily",
    )
    db_session.add(page)
    await db_session.flush()

    events = [
        # 3 rapid events for same model (triggers rapid_iteration)
        EventRecord(
            source_id=source.id,
            page_id=page.id,
            title="Model-X v1",
            normalized_title="model-x v1",
            organization="TestOrg",
            source_type="product-news index",
            canonical_path="/news/1",
            event_type="model_release",
            model_slug="model-x",
            observed_at=now - timedelta(days=1),
        ),
        EventRecord(
            source_id=source.id,
            page_id=page.id,
            title="Model-X v2",
            normalized_title="model-x v2",
            organization="TestOrg",
            source_type="product-news index",
            canonical_path="/news/2",
            event_type="api_update",
            model_slug="model-x",
            observed_at=now - timedelta(days=1),
        ),
        EventRecord(
            source_id=source.id,
            page_id=page.id,
            title="Model-X v3",
            normalized_title="model-x v3",
            organization="TestOrg",
            source_type="product-news index",
            canonical_path="/news/3",
            event_type="announcement",
            model_slug="model-x",
            observed_at=now - timedelta(hours=12),
        ),
        # Price drop event
        EventRecord(
            source_id=source.id,
            page_id=page.id,
            title="Model-X Price Drop",
            normalized_title="model-x price drop",
            organization="TestOrg",
            source_type="pricing",
            canonical_path="/pricing",
            event_type="pricing_change",
            model_slug="model-x",
            observed_at=now - timedelta(hours=6),
            raw_content="Model-X prices have been reduced by 30%",
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()
    return events


@pytest.fixture
async def conflicting_claim(db_session, anomaly_events):
    """Create a conflicted claim."""
    claim = ClaimRecord(
        event_id=anomaly_events[0].id,
        claim_text="Model-X performance disputed",
        source_type="news",
        source_name="Reuters",
        confidence_tier="high_secondary",
        confirmation_status="conflicted",
        observed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(claim)
    await db_session.flush()
    return claim


# --- detect_anomalies ---


@pytest.mark.asyncio
async def test_detect_anomalies_rapid_iteration(db_session, anomaly_events):
    """Detects rapid iteration (3+ events for same model)."""
    insights = await detect_anomalies(db_session, window_days=7)
    rapid = [i for i in insights if i.insight_type == "rapid_iteration"]
    assert len(rapid) >= 1
    assert rapid[0].related_model_slug == "model-x"


@pytest.mark.asyncio
async def test_detect_anomalies_price_drop(db_session, anomaly_events):
    """Detects price drops from raw_content keywords."""
    insights = await detect_anomalies(db_session, window_days=7)
    drops = [i for i in insights if i.insight_type == "price_drop"]
    assert len(drops) >= 1
    assert drops[0].related_model_slug == "model-x"


@pytest.mark.asyncio
async def test_detect_anomalies_conflict(db_session, anomaly_events, conflicting_claim):
    """Detects conflicting claims."""
    insights = await detect_anomalies(db_session, window_days=7)
    conflicts = [i for i in insights if i.insight_type == "conflict_detected"]
    assert len(conflicts) >= 1
    assert conflicts[0].severity == "critical"


@pytest.mark.asyncio
async def test_detect_anomalies_new_model(db_session, anomaly_events):
    """Detects new model families."""
    insights = await detect_anomalies(db_session, window_days=7)
    new_models = [i for i in insights if i.insight_type == "new_model"]
    # model-x is new (no older events exist)
    assert len(new_models) >= 1


@pytest.mark.asyncio
async def test_detect_anomalies_idempotent(db_session, anomaly_events):
    """Running detection twice doesn't create duplicate insights."""
    await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    second = await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    assert len(second) == 0  # all already exist


@pytest.mark.asyncio
async def test_detect_anomalies_persisted(db_session, anomaly_events):
    """Insights are persisted to the database."""
    insights = await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    assert len(insights) > 0
    # Verify they're in the DB
    stored = await get_recent_insights(db_session, limit=50)
    assert len(stored) >= len(insights)


@pytest.mark.asyncio
async def test_detect_anomalies_empty(db_session):
    """No events means no anomalies."""
    insights = await detect_anomalies(db_session, window_days=7)
    assert insights == []


# --- get_recent_insights ---


@pytest.mark.asyncio
async def test_get_recent_insights_empty(db_session):
    """Returns empty list when no insights exist."""
    insights = await get_recent_insights(db_session, limit=20)
    assert insights == []


@pytest.mark.asyncio
async def test_get_recent_insights_filter_severity(db_session, anomaly_events):
    """Can filter by severity."""
    await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    info_insights = await get_recent_insights(db_session, severity="info")
    for insight in info_insights:
        assert insight.severity == "info"


@pytest.mark.asyncio
async def test_get_recent_insights_filter_type(db_session, anomaly_events):
    """Can filter by insight_type."""
    await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    rapid = await get_recent_insights(db_session, insight_type="rapid_iteration")
    for insight in rapid:
        assert insight.insight_type == "rapid_iteration"


@pytest.mark.asyncio
async def test_get_recent_insights_limit(db_session, anomaly_events):
    """Limit restricts results."""
    await detect_anomalies(db_session, window_days=7)
    await db_session.commit()

    limited = await get_recent_insights(db_session, limit=1)
    assert len(limited) <= 1
