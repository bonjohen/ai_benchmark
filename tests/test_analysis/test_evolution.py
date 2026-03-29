"""Tests for evolution service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.evolution import (
    _compute_saturation,
    get_benchmark_evolution,
)


@pytest.mark.asyncio
async def test_evolution_empty_db(db_session):
    """Evolution on empty DB returns empty list."""
    result = await get_benchmark_evolution(db_session, window_days=180)
    assert result == []


@pytest.mark.asyncio
async def test_evolution_single_benchmark(db_session, multi_org_events, multi_org_claims):
    """Evolution for a specific benchmark returns one summary."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    assert len(result) == 1
    assert result[0].benchmark_name == "SWE-bench Verified"


@pytest.mark.asyncio
async def test_evolution_all_benchmarks(db_session, multi_org_events, multi_org_claims):
    """Evolution without benchmark_name returns summaries for all benchmarks."""
    result = await get_benchmark_evolution(db_session, window_days=180)
    names = {s.benchmark_name for s in result}
    assert "SWE-bench Verified" in names
    assert "MMLU" in names


@pytest.mark.asyncio
async def test_evolution_rate_computation(db_session, multi_org_events, multi_org_claims):
    """Evolution computes improvement rate."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    summary = result[0]
    # We have gpt-4o at 71.5% and gpt-5 at 92.3%
    assert summary.total_improvement is not None
    assert summary.total_improvement > 0
    assert summary.improvement_rate_per_month is not None


@pytest.mark.asyncio
async def test_evolution_frontier_progression(db_session, multi_org_events, multi_org_claims):
    """Evolution builds frontier of record-breaking scores."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    summary = result[0]
    assert len(summary.frontier) >= 1
    # Frontier should be in chronological order with increasing scores
    for i in range(len(summary.frontier) - 1):
        assert summary.frontier[i].score < summary.frontier[i + 1].score


@pytest.mark.asyncio
async def test_evolution_saturation_percentage(db_session, multi_org_events, multi_org_claims):
    """Saturation computed for percentage-based benchmarks."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    summary = result[0]
    # SWE-bench scores are percentages (<=100), so saturation should be computed
    if summary.current_top_score is not None:
        assert summary.saturation_pct is not None
        assert 0 < summary.saturation_pct <= 100


def test_saturation_none_for_elo():
    """Saturation returns None for ELO-like benchmarks."""
    assert _compute_saturation(1287.0, "LMArena Elo") is None
    assert _compute_saturation(1350.0, "arena-hard") is None


def test_saturation_none_for_high_scores():
    """Saturation returns None for scores in ELO range."""
    assert _compute_saturation(1500.0, "Some Benchmark") is None


@pytest.mark.asyncio
async def test_evolution_gap_to_second(db_session, multi_org_events, multi_org_claims):
    """Evolution computes gap between first and second place."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    summary = result[0]
    if summary.models_evaluated >= 2:
        assert summary.gap_to_second is not None
        assert summary.gap_to_second >= 0


@pytest.mark.asyncio
async def test_evolution_current_leader(db_session, multi_org_events, multi_org_claims):
    """Evolution identifies the current leader."""
    result = await get_benchmark_evolution(
        db_session, benchmark_name="SWE-bench Verified", window_days=180
    )
    summary = result[0]
    assert summary.current_leader == "gpt-5"
    assert summary.current_top_score == pytest.approx(92.3)
