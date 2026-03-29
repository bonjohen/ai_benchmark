"""Low-value page filtering with date validation and change-ratio thresholds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from .normalizer import extract_date

if TYPE_CHECKING:
    from ..collection.differ import DiffResult
    from ..config.settings import PageConfig
    from ..sources.base import RawItem

logger = structlog.get_logger()


def has_recent_date(items: list[RawItem], max_age_days: int = 90) -> bool:
    """Check if at least one item has a date within the threshold."""
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for item in items:
        date_str = extract_date(item.date_text or item.body)
        if date_str and date_str >= cutoff_str:
            return True
    return False


def is_low_value_page(
    diff: DiffResult,
    items: list[RawItem],
    page: PageConfig,
    times_polled: int = 0,
) -> bool:
    """Determine if a page's extracted items are low-value noise.

    Criteria:
    - Trivial change on a stable page (change_ratio < 0.01 and polled > 5 times)
    - No items contain a date within the last 90 days (stale content)
    - All extracted titles are shorter than 5 characters (garbage extraction)

    On cold start (change_ratio == 1.0, no prior snapshot), the stale-date check
    is skipped to avoid discarding legitimate first-run data.
    """
    if not items:
        return False

    # Trivial change on stable page
    if diff and diff.change_ratio is not None and diff.change_ratio < 0.01 and times_polled > 5:
        logger.debug(
            "low_value_trivial_change", page=page.canonical_url, change_ratio=diff.change_ratio
        )
        return True

    # All titles too short (garbage extraction)
    if all(len(item.title.strip()) < 5 for item in items):
        logger.debug("low_value_short_titles", page=page.canonical_url)
        return True

    # No recent dates — skip on cold start (no prior snapshot) and for page types
    # that inherently don't contain dates (leaderboards, model catalogs, pricing)
    is_cold_start = diff and diff.change_ratio is not None and diff.change_ratio >= 1.0
    dateless_page_types = {"leaderboard", "model catalog", "pricing", "methodology"}
    skip_date_check = is_cold_start or (page.page_type in dateless_page_types)
    if not skip_date_check and not has_recent_date(items):
        logger.debug("low_value_stale_dates", page=page.canonical_url)
        return True

    return False
