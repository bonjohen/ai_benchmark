"""Tests for the normalizer module — extract_date ISO 8601 handling."""

from __future__ import annotations

from ai_benchmark.processing.normalizer import extract_date


def test_extract_date_iso8601_with_time():
    """extract_date handles ISO 8601 timestamps with T separator."""
    assert extract_date("2026-03-29T15:00:00.000Z") == "2026-03-29"


def test_extract_date_iso8601_no_millis():
    """extract_date handles ISO 8601 without milliseconds."""
    assert extract_date("2026-03-29T15:00:00Z") == "2026-03-29"


def test_extract_date_iso8601_no_z():
    """extract_date handles ISO 8601 without timezone marker."""
    assert extract_date("2026-03-29T15:00:00") == "2026-03-29"


def test_extract_date_plain_iso():
    """extract_date still handles plain ISO dates."""
    assert extract_date("2026-03-29") == "2026-03-29"


def test_extract_date_iso_in_text():
    """extract_date finds ISO date embedded in text."""
    assert extract_date("Published on 2026-03-29 by author") == "2026-03-29"


def test_extract_date_iso8601_in_text():
    """extract_date finds ISO 8601 timestamp embedded in text."""
    assert extract_date("created_at: 2026-03-29T12:30:00.000Z, updated") == "2026-03-29"


def test_extract_date_month_name_format():
    """extract_date preserves existing month-name format parsing."""
    result = extract_date("March 29, 2026")
    assert result == "2026-03-29"


def test_extract_date_no_date():
    """extract_date returns None when no date found."""
    assert extract_date("No date here at all") is None


def test_extract_date_empty_string():
    """extract_date handles empty string."""
    assert extract_date("") is None


def test_extract_date_old_date():
    """extract_date extracts old dates correctly (does not filter by age)."""
    assert extract_date("2020-01-15") == "2020-01-15"


def test_extract_date_iso8601_prefers_first():
    """When multiple dates present, ISO 8601 with T is found first."""
    text = "2026-03-29T10:00:00Z and also 2026-04-01"
    assert extract_date(text) == "2026-03-29"
