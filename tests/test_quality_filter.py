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


# --- Phase 1: dateless_page_types expansion and candidate_paper exemption ---


def _make_page_with_type(page_type: str) -> PageConfig:
    return PageConfig(canonical_url="https://example.com", page_type=page_type)


def test_not_low_value_papers_index():
    """papers index page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Some paper about LLMs", body="No date here")]
    page = _make_page_with_type("papers index")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_trending_papers():
    """trending papers page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Trending paper about safety", body="Abstract text")]
    page = _make_page_with_type("trending papers")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_recent_submissions():
    """recent submissions page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="arXiv paper on benchmarks", body="Authors list")]
    page = _make_page_with_type("recent submissions")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_forum_index():
    """forum index page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Forum topic about models", body="")]
    page = _make_page_with_type("forum index")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_discourse_json():
    """discourse json page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Forum topic", body="")]
    page = _make_page_with_type("discourse json")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_leaderboard_docs():
    """leaderboard docs page type is exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Open LLM Leaderboard", body="Documentation")]
    page = _make_page_with_type("leaderboard docs")
    assert is_low_value_page(diff, items, page) is False


def test_not_low_value_candidate_papers():
    """Pages producing only candidate_paper items are exempt from stale date check."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [
        RawItem(title="Paper A", body="No date", item_type="candidate_paper"),
        RawItem(title="Paper B", body="No date", item_type="candidate_paper"),
    ]
    # Use a page type NOT in dateless_page_types to prove the item-type exemption works
    page = _make_page_with_type("unknown_type")
    assert is_low_value_page(diff, items, page) is False


def test_low_value_mixed_items_no_date():
    """Mixed item types (not all candidate_paper) still filtered when stale."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [
        RawItem(title="Paper A", body="No date", item_type="candidate_paper"),
        RawItem(title="News B", body="No date", item_type="news_article"),
    ]
    page = _make_page_with_type("unknown_type")
    assert is_low_value_page(diff, items, page) is True


def test_existing_leaderboard_exemption_still_works():
    """Original leaderboard page type exemption is preserved."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="Model scores", body="No date")]
    page = _make_page_with_type("leaderboard")
    assert is_low_value_page(diff, items, page) is False


def test_trivial_change_filter_unchanged():
    """Trivial change filter still works after page-type expansion."""
    diff = DiffResult(changed=True, change_ratio=0.005)
    items = [RawItem(title="Some item", body="2026-03-28 change")]
    page = _make_page_with_type("papers index")
    assert is_low_value_page(diff, items, page, times_polled=10) is True


def test_short_title_filter_unchanged():
    """Short title filter still works after page-type expansion."""
    diff = DiffResult(changed=True, change_ratio=0.5)
    items = [RawItem(title="ab", body=""), RawItem(title="cd", body="")]
    page = _make_page_with_type("papers index")
    assert is_low_value_page(diff, items, page) is True
