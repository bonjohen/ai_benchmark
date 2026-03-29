"""Tests for benchmark trends service."""

from __future__ import annotations

import pytest

from ai_benchmark.analysis.services.benchmark_trends import (
    extract_benchmark_score,
    get_benchmark_leaderboard,
    get_benchmark_timeline,
    list_benchmarks,
)

# --- extract_benchmark_score ---


def test_extract_percentage():
    """Extracts percentage-style scores."""
    assert extract_benchmark_score("scored 92.3% on SWE-bench") == 92.3


def test_extract_percentage_integer():
    """Handles integer percentages."""
    assert extract_benchmark_score("achieves 85% accuracy") == 85.0


def test_extract_elo():
    """Extracts Elo-like scores."""
    assert extract_benchmark_score("Elo: 1287") == 1287.0


def test_extract_rating():
    """Extracts rating-style scores."""
    assert extract_benchmark_score("rating: 1350.5") == 1350.5


def test_extract_score_keyword():
    """Extracts 'score: X' pattern."""
    assert extract_benchmark_score("score: 85.1") == 85.1


def test_extract_decimal_fraction():
    """Extracts decimal fractions between 0 and 1."""
    assert extract_benchmark_score("achieved 0.623 on the task") == 0.623


def test_extract_bare_integer():
    """Falls back to bare 2-4 digit integers."""
    assert extract_benchmark_score("the model got 1287 points") == 1287.0


def test_extract_none_on_empty():
    """Returns None for empty content."""
    assert extract_benchmark_score("") is None
    assert extract_benchmark_score("no numbers here") is None


def test_extract_priority_percentage_over_elo():
    """Percentage takes priority over Elo pattern."""
    assert extract_benchmark_score("scored 92.3% with Elo: 1287") == 92.3


def test_extract_with_benchmark_name():
    """benchmark_name parameter doesn't break extraction."""
    result = extract_benchmark_score("72.3% on SWE-bench Verified", "SWE-bench")
    assert result == 72.3


# --- list_benchmarks ---


@pytest.mark.asyncio
async def test_list_benchmarks(db_session, sample_events):
    """list_benchmarks returns benchmarks with entry counts."""
    benchmarks = await list_benchmarks(db_session)
    assert len(benchmarks) == 1  # only SWE-bench Verified event has benchmark_variant
    assert benchmarks[0].benchmark_name == "SWE-bench Verified"
    assert benchmarks[0].entry_count == 1


@pytest.mark.asyncio
async def test_list_benchmarks_empty(db_session):
    """Returns empty list when no benchmark events exist."""
    benchmarks = await list_benchmarks(db_session)
    assert benchmarks == []


@pytest.mark.asyncio
async def test_list_benchmarks_score_extraction(db_session, sample_events):
    """list_benchmarks extracts top score from raw_content."""
    benchmarks = await list_benchmarks(db_session)
    assert len(benchmarks) == 1
    # raw_content is "GPT-5 achieves 72.3% on SWE-bench Verified"
    assert benchmarks[0].top_score == 72.3
    assert benchmarks[0].top_model == "gpt-5"


# --- get_benchmark_leaderboard ---


@pytest.mark.asyncio
async def test_get_benchmark_leaderboard(db_session, sample_events):
    """get_benchmark_leaderboard returns ranked entries."""
    leaderboard = await get_benchmark_leaderboard(db_session, "SWE-bench")
    assert leaderboard.benchmark_name == "SWE-bench"
    assert len(leaderboard.entries) == 1
    assert leaderboard.entries[0].model_slug == "gpt-5"


@pytest.mark.asyncio
async def test_get_benchmark_leaderboard_score(db_session, sample_events):
    """Leaderboard entries have extracted scores."""
    leaderboard = await get_benchmark_leaderboard(db_session, "SWE-bench")
    assert leaderboard.entries[0].score == 72.3


@pytest.mark.asyncio
async def test_get_benchmark_leaderboard_empty(db_session, sample_events):
    """Returns empty leaderboard for unknown benchmark."""
    leaderboard = await get_benchmark_leaderboard(db_session, "NonexistentBench")
    assert leaderboard.entries == []


# --- get_benchmark_timeline ---


@pytest.mark.asyncio
async def test_get_benchmark_timeline(db_session, sample_events):
    """get_benchmark_timeline returns time-ordered data points."""
    timeline = await get_benchmark_timeline(db_session, "SWE-bench")
    assert len(timeline) == 1
    assert timeline[0].model_slug == "gpt-5"
    assert timeline[0].score == 72.3


@pytest.mark.asyncio
async def test_get_benchmark_timeline_filter_model(db_session, sample_events):
    """Timeline can be filtered by model slug."""
    timeline = await get_benchmark_timeline(db_session, "SWE-bench", model_slug="gpt-5")
    assert len(timeline) == 1

    timeline = await get_benchmark_timeline(db_session, "SWE-bench", model_slug="nonexistent")
    assert len(timeline) == 0


@pytest.mark.asyncio
async def test_get_benchmark_timeline_empty(db_session):
    """Returns empty list when no matching events."""
    timeline = await get_benchmark_timeline(db_session, "SWE-bench")
    assert timeline == []
