"""Data assembly queries for the daily intelligence report."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..models.events import EventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ─── Data structures ───


@dataclass
class Article:
    """A compact article for the daily report."""

    title: str
    publisher: str
    date: str | None
    model: str | None
    abstract: str
    url: str
    confirmed: bool
    sources: int


@dataclass
class DailyReport:
    generated_at: datetime
    articles: list[Article]


# ─── Noise filtering ───

_AI_REPO_PATTERNS = [
    "claude",
    "anthropic",
    "openai",
    "codex",
    "gpt",
    "gemini",
    "adk",
    "llama",
    "mistral",
    "cohere",
    "deepseek",
    "grok",
    "xai-sdk",
    "swe-bench",
    "agent",
    "langchain",
    "vllm",
    "transformers",
]

_CONFIDENCE_RANK = {
    "official_self_report": 0,
    "benchmark_owner_report": 1,
    "high_secondary": 2,
    "medium_discovery": 3,
    "low_discovery": 4,
}

# Leaderboard scrape pattern: per-row entries from LMArena, Artificial Analysis,
# SWE-bench, etc. Body looks like "Rank: 1, Score: 1504, Variant: arena_elo".
# These are statistics, not news articles, and shouldn't be summarized one by one.
_LEADERBOARD_BODY_RE = re.compile(r"^Rank:\s*\d+,\s*Score:")

# Google News RSS default description that appears when the feed has no real
# per-item description. The pipeline's RSS enrichment is supposed to replace
# this with the article's og:description, but enrichment skips items whose
# title is short enough that body-minus-title still exceeds the 30-char
# threshold — leaving the placeholder behind.
_GOOGLE_NEWS_PLACEHOLDER = (
    "Comprehensive up-to-date news coverage, aggregated from sources all "
    "over the world by Google News."
)


def _extract_abstract(raw_content: str | None, title: str) -> str:
    """Extract a readable abstract from raw_content, truncated to 200 chars."""
    if not raw_content:
        return ""

    text = raw_content.strip()
    if text == title or len(text) < 20:
        return ""

    # Take first 200 chars, trim to last sentence boundary
    excerpt = text[:200]
    if len(text) > 200:
        for sep in (". ", ".\n", "\n\n"):
            last = excerpt.rfind(sep)
            if last > 60:
                excerpt = excerpt[: last + 1]
                break

    return excerpt.strip()


def _is_noise(event: EventRecord) -> bool:
    """Return True if this event should be excluded from the report."""
    title = (event.title or "").strip()

    # Short titles are page chrome or fragments
    if len(title) <= 10:
        return True

    # RSS title-only: no useful abstract (nothing to summarize beyond the title)
    abstract = _extract_abstract(event.raw_content, title)
    if not abstract:
        return True

    # Leaderboard scrape rows are statistics, not articles. The benchmark
    # collectors emit one event per row with body = "Rank: N, Score: ...".
    # These overwhelm the report (60%+ of high-volume days) without adding
    # any narrative content.
    if _LEADERBOARD_BODY_RE.match(abstract):
        return True

    # Google News RSS placeholder description — the pipeline's enrichment
    # didn't replace the default feed text, so there's no real abstract.
    if abstract.strip() == _GOOGLE_NEWS_PLACEHOLDER:
        return True

    # GitHub events must match AI repo patterns
    if "github.com" in (event.canonical_path or "").lower():
        text = f"{title} {event.canonical_path or ''}".lower()
        if not any(p in text for p in _AI_REPO_PATTERNS):
            return True

    return False


def _build_article(event: EventRecord) -> Article:
    """Convert an EventRecord with loaded claims into a compact Article."""
    abstract = _extract_abstract(event.raw_content, event.title)

    # Derive metadata from claims
    source_names: set[str] = set()
    confirmed = False
    for c in event.claims:
        source_names.add(c.source_name)
        if c.confirmation_status == "confirmed":
            confirmed = True

    return Article(
        title=event.title,
        publisher=event.organization,
        date=event.published_date,
        model=event.model_slug,
        abstract=abstract,
        url=event.canonical_path or "",
        confirmed=confirmed,
        sources=len(source_names),
    )


# ─── Queries ───


async def _fetch_events_in_date_range(
    session: AsyncSession,
    date_from: str,
    date_to: str,
) -> list[Article]:
    """Fetch events first observed in [date_from, date_to], noise-filtered.

    Scopes by ``date(observed_at)`` rather than ``published_date`` because most
    leaderboard rows and many scraped pages have no parseable publication date.
    ``observed_at`` is always set on first creation (see processing/pipeline.py)
    and represents the first time the pipeline encountered the event, which is
    the right semantic for a daily intelligence report.
    """
    observed_day = func.date(EventRecord.observed_at)
    stmt = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .where(
            observed_day >= date_from,
            observed_day <= date_to,
        )
        .order_by(EventRecord.observed_at.desc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().unique().all())

    return [_build_article(e) for e in events if not _is_noise(e)]


# ─── Public API ───


async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
    reference_date: date | None = None,
) -> DailyReport:
    """Assemble the daily report: noise-filtered articles from a date or recent window.

    When *reference_date* is provided the query window is that single calendar
    day and *hours* is ignored.  Otherwise the window spans the last *hours*
    hours from now.
    """
    if reference_date is not None:
        day_str = reference_date.isoformat()
        articles = await _fetch_events_in_date_range(session, day_str, day_str)
        generated_at = datetime.combine(reference_date, datetime.min.time(), tzinfo=UTC)
    else:
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d")
        articles = await _fetch_events_in_date_range(session, cutoff, today)
        generated_at = now

    return DailyReport(
        generated_at=generated_at,
        articles=articles,
    )
