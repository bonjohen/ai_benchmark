"""Tests for analysis ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_benchmark.analysis.models import AnalysisInsight, AnalysisSnapshot


@pytest.mark.asyncio
async def test_analysis_snapshot_creation(db_session):
    """AnalysisSnapshot can be created with required fields."""
    snap = AnalysisSnapshot(
        analysis_type="model_lifecycle",
        scope_key="gpt-5",
        result_json='{"model_slug": "gpt-5"}',
        event_count=10,
        version=1,
    )
    db_session.add(snap)
    await db_session.flush()

    assert snap.id is not None
    assert snap.analysis_type == "model_lifecycle"
    assert snap.scope_key == "gpt-5"
    assert snap.event_count == 10
    assert snap.computed_at is not None


@pytest.mark.asyncio
async def test_analysis_snapshot_optional_window(db_session):
    """AnalysisSnapshot window fields are optional."""
    snap = AnalysisSnapshot(
        analysis_type="digest",
        scope_key="weekly-2026-W13",
        result_json="{}",
        window_start=datetime(2026, 3, 23, tzinfo=UTC),
        window_end=datetime(2026, 3, 29, tzinfo=UTC),
    )
    db_session.add(snap)
    await db_session.flush()

    assert snap.window_start is not None
    assert snap.window_end is not None


@pytest.mark.asyncio
async def test_analysis_insight_creation(db_session):
    """AnalysisInsight can be created with required fields."""
    insight = AnalysisInsight(
        insight_type="new_model",
        severity="notable",
        title="New model: GPT-5",
        description="First event observed for model slug gpt-5.",
        related_model_slug="gpt-5",
        related_org="OpenAI",
        related_event_ids="1,2,3",
    )
    db_session.add(insight)
    await db_session.flush()

    assert insight.id is not None
    assert insight.insight_type == "new_model"
    assert insight.severity == "notable"
    assert insight.detected_at is not None


@pytest.mark.asyncio
async def test_analysis_insight_with_snapshot_fk(db_session):
    """AnalysisInsight can reference a snapshot."""
    snap = AnalysisSnapshot(
        analysis_type="anomalies",
        scope_key="global",
        result_json="{}",
    )
    db_session.add(snap)
    await db_session.flush()

    insight = AnalysisInsight(
        insight_type="benchmark_record",
        severity="info",
        title="New record on SWE-bench",
        description="Score 72.3% exceeds previous max.",
        snapshot_id=snap.id,
    )
    db_session.add(insight)
    await db_session.flush()

    assert insight.snapshot_id == snap.id


@pytest.mark.asyncio
async def test_analysis_insight_nullable_fields(db_session):
    """AnalysisInsight nullable fields default to None."""
    insight = AnalysisInsight(
        insight_type="price_drop",
        severity="info",
        title="Price drop detected",
        description="GPT-5 pricing decreased.",
    )
    db_session.add(insight)
    await db_session.flush()

    assert insight.related_event_ids is None
    assert insight.related_model_slug is None
    assert insight.related_org is None
    assert insight.snapshot_id is None
