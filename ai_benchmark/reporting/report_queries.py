"""Data assembly queries for the daily intelligence report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
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
    """Fetch events with published_date in [date_from, date_to], noise-filtered."""
    stmt = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .where(
            EventRecord.published_date.isnot(None),
            EventRecord.published_date >= date_from,
            EventRecord.published_date <= date_to,
        )
        .order_by(EventRecord.published_date.desc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().unique().all())

    return [_build_article(e) for e in events if not _is_noise(e)]


# ─── Public API ───


async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
) -> DailyReport:
    """Assemble the daily report: noise-filtered articles from the last 24h."""
    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d")

    articles = await _fetch_events_in_date_range(session, cutoff, today)

    return DailyReport(
        generated_at=now,
        articles=articles,
    )
