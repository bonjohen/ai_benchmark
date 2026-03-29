"""Tests for spotlight service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.spotlight import get_spotlight


@pytest.mark.asyncio
async def test_spotlight_empty_db(db_session):
    """Spotlight on empty DB returns empty report."""
    report = await get_spotlight(db_session, window_days=30)
    assert report.total_new_models == 0
    assert report.entries == []


@pytest.mark.asyncio
async def test_spotlight_single_model(db_session, multi_org_events, multi_org_claims):
    """Spotlight finds new models with benchmark data."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=0)
    assert report.total_new_models >= 1
    slugs = {e.model_slug for e in report.entries}
    # GPT-5, claude-4-sonnet, and gpt-4o should appear (all within 30 days of now)
    assert "gpt-5" in slugs


@pytest.mark.asyncio
async def test_spotlight_multiple_models(db_session, multi_org_events, multi_org_claims):
    """Spotlight returns models from both orgs."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=0)
    orgs = {e.organization for e in report.entries}
    assert "OpenAI" in orgs
    assert "Anthropic" in orgs


@pytest.mark.asyncio
async def test_spotlight_min_benchmarks_filter(db_session, multi_org_events, multi_org_claims):
    """min_benchmarks filters out models with fewer benchmark entries."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=2)
    for entry in report.entries:
        assert entry.benchmark_count >= 2


@pytest.mark.asyncio
async def test_spotlight_org_filter(db_session, multi_org_events, multi_org_claims):
    """Organization filter restricts results."""
    report = await get_spotlight(
        db_session, window_days=30, organization="Anthropic", min_benchmarks=0
    )
    for entry in report.entries:
        assert entry.organization == "Anthropic"


@pytest.mark.asyncio
async def test_spotlight_debut_strength_ranking(db_session, multi_org_events, multi_org_claims):
    """Entries are sorted by debut_strength descending."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=0)
    if len(report.entries) >= 2:
        for i in range(len(report.entries) - 1):
            assert report.entries[i].debut_strength >= report.entries[i + 1].debut_strength


@pytest.mark.asyncio
async def test_spotlight_xref_count(
    db_session, multi_org_events, multi_org_claims, multi_org_xrefs
):
    """Spotlight counts cross-references for models."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=0)
    gpt5 = next((e for e in report.entries if e.model_slug == "gpt-5"), None)
    assert gpt5 is not None
    # GPT-5 has confirms xrefs in the fixtures
    assert gpt5.xref_count >= 1


@pytest.mark.asyncio
async def test_spotlight_best_scores(db_session, multi_org_events, multi_org_claims):
    """Spotlight extracts best scores per benchmark."""
    report = await get_spotlight(db_session, window_days=30, min_benchmarks=0)
    gpt5 = next((e for e in report.entries if e.model_slug == "gpt-5"), None)
    assert gpt5 is not None
    assert "SWE-bench Verified" in gpt5.best_scores
    assert gpt5.best_scores["SWE-bench Verified"] == pytest.approx(92.3)
