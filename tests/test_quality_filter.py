"""Tests for the quality filter module."""

from __future__ import annotations

from ai_benchmark.collection.differ import DiffResult
from ai_benchmark.config.settings import PageConfig
from ai_benchmark.processing.quality_filter import has_recent_date, is_low_value_page
from ai_benchmark.sources.base import RawItem


def _make_page(url: str = "https://example.com") -> PageConfig:
    return PageConfig(canonical_url=url, page_type="test")


def test_low_value_trivial_change_stable():
    """Trivial change on a stable page is low value."""
    diff = DiffResult(changed=True, change_ratio=0.005)
    items = [RawItem(title="Some item", body="2026-03-28 change")]
    assert is_low_value_page(diff, items, _make_page(), times_polled=10) is True


def test_not_low_value_meaningful_change():
    """Meaningful change is not low value."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="GPT-5 released on 2026-03-28", body="2026-03-28")]
    assert is_low_value_page(diff, items, _make_page(), times_polled=10) is False


def test_low_value_short_titles():
    """All short titles is low value."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="ab", body="2026-03-28"), RawItem(title="cd", body="2026-03-28")]
    assert is_low_value_page(diff, items, _make_page()) is True


def test_low_value_stale_dates():
    """All stale dates is low value."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Old event from 2020-01-01", body="2020-01-01")]
    assert is_low_value_page(diff, items, _make_page()) is True


def test_not_low_value_recent_dates():
    """Recent dates are not low value."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="New event on 2026-03-15", body="2026-03-15")]
    assert is_low_value_page(diff, items, _make_page()) is False


def test_not_low_value_empty_items():
    """Empty items list is not low value (nothing to filter)."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    assert is_low_value_page(diff, [], _make_page()) is False


def test_has_recent_date_iso():
    """has_recent_date detects ISO format dates."""
    items = [RawItem(title="Event", date_text="2026-03-15")]
    assert has_recent_date(items) is True


def test_has_recent_date_in_body():
    """has_recent_date extracts date from body."""
    items = [RawItem(title="Event", body="Published on 2026-03-15")]
    assert has_recent_date(items) is True


def test_has_recent_date_stale():
    """has_recent_date returns False for old dates."""
    items = [RawItem(title="Event", body="Published on 2020-01-01")]
    assert has_recent_date(items) is False


def test_has_recent_date_no_date():
    """has_recent_date returns False when no dates found."""
    items = [RawItem(title="Event", body="No date here")]
    assert has_recent_date(items) is False
