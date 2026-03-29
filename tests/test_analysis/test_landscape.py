"""Tests for landscape service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.landscape import get_landscape


@pytest.mark.asyncio
async def test_landscape_empty_db(db_session):
    """Landscape on empty DB returns empty report."""
    report = await get_landscape(db_session, window_days=30)
    assert report.entries == []


@pytest.mark.asyncio
async def test_landscape_single_org(db_session, multi_org_events, multi_org_claims):
    """Landscape filtered to one org returns one entry."""
    report = await get_landscape(db_session, window_days=30, organization="OpenAI")
    assert len(report.entries) == 1
    assert report.entries[0].organization == "OpenAI"


@pytest.mark.asyncio
async def test_landscape_multi_org(db_session, multi_org_events, multi_org_claims):
    """Landscape includes all active organizations."""
    report = await get_landscape(db_session, window_days=30)
    orgs = {e.organization for e in report.entries}
    assert "OpenAI" in orgs
    assert "Anthropic" in orgs


@pytest.mark.asyncio
async def test_landscape_new_model_detection(db_session, multi_org_events, multi_org_claims):
    """Landscape detects new models within window."""
    report = await get_landscape(db_session, window_days=30)
    openai = next((e for e in report.entries if e.organization == "OpenAI"), None)
    assert openai is not None
    assert openai.new_models >= 1


@pytest.mark.asyncio
async def test_landscape_pricing_events(db_session, multi_org_events, multi_org_claims):
    """Landscape counts pricing events."""
    report = await get_landscape(db_session, window_days=30)
    openai = next((e for e in report.entries if e.organization == "OpenAI"), None)
    assert openai is not None
    assert openai.pricing_events >= 1


@pytest.mark.asyncio
async def test_landscape_benchmark_breadth(db_session, multi_org_events, multi_org_claims):
    """Landscape computes benchmark breadth per org."""
    report = await get_landscape(db_session, window_days=30)
    openai = next((e for e in report.entries if e.organization == "OpenAI"), None)
    assert openai is not None
    # OpenAI has SWE-bench Verified and MMLU events
    assert openai.benchmark_breadth >= 1


@pytest.mark.asyncio
async def test_landscape_trend(db_session, multi_org_events, multi_org_claims):
    """Landscape computes trend relative to prior window."""
    report = await get_landscape(db_session, window_days=30)
    for entry in report.entries:
        assert entry.trend in ("up", "down", "stable")
