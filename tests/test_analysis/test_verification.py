"""Tests for verification service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.verification import get_verification_report


@pytest.mark.asyncio
async def test_verification_empty_db(db_session):
    """Verification on empty DB returns zeros."""
    report = await get_verification_report(db_session)
    assert report.total_events == 0
    assert report.total_claims == 0
    assert report.confirmation_rate == 0.0


@pytest.mark.asyncio
async def test_verification_model_counts(db_session, multi_org_events, multi_org_claims):
    """Verification report counts events and claims."""
    report = await get_verification_report(db_session)
    assert report.total_events >= 1
    assert report.total_claims >= 1


@pytest.mark.asyncio
async def test_verification_confirmed_pct(db_session, multi_org_events, multi_org_claims):
    """Confirmation rate reflects confirmed claims."""
    report = await get_verification_report(db_session)
    assert 0.0 <= report.confirmation_rate <= 100.0


@pytest.mark.asyncio
async def test_verification_conflicted_pct(db_session, multi_org_events, multi_org_claims):
    """Conflict rate reflects conflicted claims."""
    report = await get_verification_report(db_session)
    assert 0.0 <= report.conflict_rate <= 100.0
    # We have at least one conflicted claim in fixtures
    assert report.conflict_rate > 0.0


@pytest.mark.asyncio
async def test_verification_model_detail(db_session, multi_org_events, multi_org_claims):
    """Per-model verification includes expected models."""
    report = await get_verification_report(db_session)
    slugs = {m.model_slug for m in report.model_verifications}
    assert "gpt-5" in slugs
    assert "claude-4-sonnet" in slugs


@pytest.mark.asyncio
async def test_verification_source_count(db_session, multi_org_events, multi_org_claims):
    """Per-model source count reflects distinct claim sources."""
    report = await get_verification_report(db_session)
    gpt5 = next((m for m in report.model_verifications if m.model_slug == "gpt-5"), None)
    assert gpt5 is not None
    assert gpt5.source_count >= 1


@pytest.mark.asyncio
async def test_verification_tier_distribution(db_session, multi_org_events, multi_org_claims):
    """Tier distribution has expected tiers."""
    report = await get_verification_report(db_session)
    assert len(report.tier_distribution) >= 1
    # We have official_self_report claims
    assert "official_self_report" in report.tier_distribution


@pytest.mark.asyncio
async def test_verification_xref_count(
    db_session, multi_org_events, multi_org_claims, multi_org_xrefs
):
    """CrossReference confirms count is populated."""
    report = await get_verification_report(db_session)
    gpt5 = next((m for m in report.model_verifications if m.model_slug == "gpt-5"), None)
    assert gpt5 is not None
    assert gpt5.xref_confirms_count >= 1


@pytest.mark.asyncio
async def test_verification_benchmark_detail(db_session, multi_org_events, multi_org_claims):
    """Benchmark verification includes expected benchmarks."""
    report = await get_verification_report(db_session)
    bvariants = {b.benchmark_variant for b in report.benchmark_verifications}
    assert "SWE-bench Verified" in bvariants


@pytest.mark.asyncio
async def test_verification_org_filter(db_session, multi_org_events, multi_org_claims):
    """Organization filter restricts results."""
    report = await get_verification_report(db_session, organization="OpenAI")
    for m in report.model_verifications:
        assert m.organization == "OpenAI"


@pytest.mark.asyncio
async def test_verification_model_filter(db_session, multi_org_events, multi_org_claims):
    """Model slug filter restricts results."""
    report = await get_verification_report(db_session, model_slug="gpt-5")
    slugs = {m.model_slug for m in report.model_verifications}
    assert slugs == {"gpt-5"}
