"""Tests for correlation service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.correlation import (
    _correlation_label,
    _rank,
    _spearman_correlation,
    get_correlation_matrix,
)


@pytest.mark.asyncio
async def test_correlation_empty_db(db_session):
    """Correlation on empty DB returns empty matrix."""
    matrix = await get_correlation_matrix(db_session)
    assert matrix.benchmark_count == 0
    assert matrix.entries == []
    assert matrix.clusters == []


@pytest.mark.asyncio
async def test_correlation_with_data(db_session, multi_org_events, multi_org_claims):
    """Correlation matrix is computed for benchmarks with sufficient overlap."""
    # min_overlap=2 since we only have 2-3 models per benchmark
    matrix = await get_correlation_matrix(db_session, min_overlap=2)
    assert matrix.benchmark_count >= 2


@pytest.mark.asyncio
async def test_correlation_entries(db_session, multi_org_events, multi_org_claims):
    """Correlation entries have expected fields."""
    matrix = await get_correlation_matrix(db_session, min_overlap=2)
    for entry in matrix.entries:
        assert -1.0 <= entry.correlation <= 1.0
        assert entry.overlap_count >= 2
        assert entry.label in ("redundant", "similar", "moderate", "distinct", "independent")


@pytest.mark.asyncio
async def test_correlation_high_min_overlap(db_session, multi_org_events, multi_org_claims):
    """High min_overlap produces no entries when data is sparse."""
    matrix = await get_correlation_matrix(db_session, min_overlap=100)
    assert matrix.entries == []


def test_spearman_perfect_correlation():
    """Perfect positive correlation returns 1.0."""
    pairs = [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0), (4.0, 40.0), (5.0, 50.0)]
    assert _spearman_correlation(pairs) == pytest.approx(1.0, abs=0.01)


def test_spearman_perfect_negative():
    """Perfect negative correlation returns -1.0."""
    pairs = [(1.0, 50.0), (2.0, 40.0), (3.0, 30.0), (4.0, 20.0), (5.0, 10.0)]
    assert _spearman_correlation(pairs) == pytest.approx(-1.0, abs=0.01)


def test_rank_with_ties():
    """Ranks handle ties with average ranking."""
    ranks = _rank([10.0, 20.0, 20.0, 30.0])
    assert ranks[0] == 1.0
    assert ranks[1] == 2.5  # tied for ranks 2 and 3
    assert ranks[2] == 2.5
    assert ranks[3] == 4.0


def test_correlation_labels():
    """Correlation labels match thresholds."""
    assert _correlation_label(0.9) == "redundant"
    assert _correlation_label(0.7) == "similar"
    assert _correlation_label(0.5) == "moderate"
    assert _correlation_label(0.2) == "distinct"
    assert _correlation_label(0.05) == "independent"
