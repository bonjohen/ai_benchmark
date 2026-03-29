"""Tests for the model lifecycle service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.model_lifecycle import (
    build_model_profile,
    compare_models,
    list_tracked_models,
)


@pytest.mark.asyncio
async def test_list_tracked_models(db_session, sample_events):
    """list_tracked_models returns summaries grouped by model_slug."""
    models = await list_tracked_models(db_session)
    assert len(models) == 2  # gpt-5 and gpt-4o-mini

    slugs = {m.model_slug for m in models}
    assert "gpt-5" in slugs
    assert "gpt-4o-mini" in slugs


@pytest.mark.asyncio
async def test_list_tracked_models_event_counts(db_session, sample_events):
    """Each model summary has the correct event count."""
    models = await list_tracked_models(db_session)
    by_slug = {m.model_slug: m for m in models}

    assert by_slug["gpt-5"].event_count == 3  # release + pricing + benchmark
    assert by_slug["gpt-4o-mini"].event_count == 1  # deprecation


@pytest.mark.asyncio
async def test_list_tracked_models_status(db_session, sample_events):
    """Status is correctly inferred from event types."""
    models = await list_tracked_models(db_session)
    by_slug = {m.model_slug: m for m in models}

    assert by_slug["gpt-5"].status == "active"
    assert by_slug["gpt-4o-mini"].status == "deprecated"


@pytest.mark.asyncio
async def test_list_tracked_models_filter_org(db_session, sample_events):
    """Organization filter returns matching models only."""
    models = await list_tracked_models(db_session, organization="OpenAI")
    assert len(models) == 2

    models = await list_tracked_models(db_session, organization="Google")
    assert len(models) == 0


@pytest.mark.asyncio
async def test_list_tracked_models_pagination(db_session, sample_events):
    """Limit and offset control result window."""
    models = await list_tracked_models(db_session, limit=1)
    assert len(models) == 1

    all_models = await list_tracked_models(db_session, limit=10, offset=0)
    offset_models = await list_tracked_models(db_session, limit=10, offset=1)
    assert len(offset_models) == len(all_models) - 1


@pytest.mark.asyncio
async def test_list_tracked_models_organization(db_session, sample_events):
    """Each summary has the correct organization."""
    models = await list_tracked_models(db_session)
    for m in models:
        assert m.organization == "OpenAI"


@pytest.mark.asyncio
async def test_build_model_profile_found(db_session, sample_events, sample_claims):
    """build_model_profile returns a full profile for existing slugs."""
    profile = await build_model_profile(db_session, "gpt-5")
    assert profile is not None
    assert profile.model_slug == "gpt-5"
    assert profile.organization == "OpenAI"
    assert profile.status == "active"


@pytest.mark.asyncio
async def test_build_model_profile_not_found(db_session, sample_events):
    """build_model_profile returns None for unknown slugs."""
    profile = await build_model_profile(db_session, "nonexistent-model")
    assert profile is None


@pytest.mark.asyncio
async def test_build_model_profile_milestones(db_session, sample_events, sample_claims):
    """Profile milestones match events in chronological order."""
    profile = await build_model_profile(db_session, "gpt-5")
    assert profile is not None
    assert len(profile.milestones) == 3  # release + pricing + benchmark

    # Milestones are ordered by observed_at asc
    types = [m.event_type for m in profile.milestones]
    assert types == ["model_release", "pricing_change", "announcement"]


@pytest.mark.asyncio
async def test_build_model_profile_claim_summary(db_session, sample_events, sample_claims):
    """Profile claim_summary aggregates confirmation statuses."""
    profile = await build_model_profile(db_session, "gpt-5")
    assert profile is not None

    # 2 confirmed claims on event[0], 1 confirmed on event[1], 1 unconfirmed on event[2]
    assert profile.claim_summary.get("confirmed", 0) == 3
    assert profile.claim_summary.get("unconfirmed", 0) == 1


@pytest.mark.asyncio
async def test_build_model_profile_benchmark_scores(db_session, sample_events, sample_claims):
    """Profile includes benchmark data points for events with benchmark_variant."""
    profile = await build_model_profile(db_session, "gpt-5")
    assert profile is not None

    # Only the SWE-bench event has benchmark_variant set
    assert len(profile.benchmark_scores) == 1
    assert profile.benchmark_scores[0].benchmark_variant == "SWE-bench Verified"


@pytest.mark.asyncio
async def test_build_model_profile_deprecated(db_session, sample_events, sample_claims):
    """Deprecated model gets correct status."""
    profile = await build_model_profile(db_session, "gpt-4o-mini")
    assert profile is not None
    assert profile.status == "deprecated"
    assert len(profile.milestones) == 1


@pytest.mark.asyncio
async def test_build_model_profile_dates(db_session, sample_events, sample_claims):
    """first_seen and latest_activity reflect published_date range."""
    profile = await build_model_profile(db_session, "gpt-5")
    assert profile is not None
    assert profile.first_seen == "2026-03-15"
    assert profile.latest_activity == "2026-03-17"


@pytest.mark.asyncio
async def test_compare_models(db_session, sample_events, sample_claims):
    """compare_models returns profiles for each requested slug."""
    matrix = await compare_models(db_session, ["gpt-5", "gpt-4o-mini"])
    assert "gpt-5" in matrix.profiles
    assert "gpt-4o-mini" in matrix.profiles
    assert matrix.model_slugs == ["gpt-5", "gpt-4o-mini"]


@pytest.mark.asyncio
async def test_compare_models_missing_slug(db_session, sample_events, sample_claims):
    """compare_models skips slugs with no events."""
    matrix = await compare_models(db_session, ["gpt-5", "nonexistent"])
    assert "gpt-5" in matrix.profiles
    assert "nonexistent" not in matrix.profiles
