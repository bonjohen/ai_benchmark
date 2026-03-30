"""Composite-key deduplication with fuzzy near-duplicate detection."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.events import EventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def find_exact_duplicate(
    session: AsyncSession,
    normalized_title: str,
    organization: str,
    source_type: str,
    canonical_path: str,
    published_date: str | None,
    model_slug: str | None = None,
) -> EventRecord | None:
    """Check for an exact composite-key duplicate (includes model_slug)."""
    stmt = select(EventRecord).where(
        EventRecord.normalized_title == normalized_title,
        EventRecord.organization == organization,
        EventRecord.source_type == source_type,
        EventRecord.canonical_path == canonical_path,
    )
    if published_date:
        stmt = stmt.where(EventRecord.published_date == published_date)
    if model_slug:
        stmt = stmt.where(EventRecord.model_slug == model_slug)
    else:
        stmt = stmt.where(EventRecord.model_slug.is_(None))
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def find_model_duplicate(
    session: AsyncSession,
    model_slug: str,
    organization: str,
    published_date: str | None,
) -> EventRecord | None:
    """Check for a duplicate by model slug + org + date."""
    if not model_slug:
        return None
    stmt = select(EventRecord).where(
        EventRecord.model_slug == model_slug,
        EventRecord.organization == organization,
    )
    if published_date:
        stmt = stmt.where(EventRecord.published_date == published_date)
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def is_near_duplicate(title_a: str, title_b: str, threshold: float = 0.85) -> bool:
    """Fuzzy near-duplicate detection using SequenceMatcher ratio."""
    return SequenceMatcher(None, title_a, title_b).ratio() >= threshold


async def find_near_duplicates(
    session: AsyncSession,
    normalized_title: str,
    organization: str,
    threshold: float = 0.85,
    limit: int = 20,
) -> list[EventRecord]:
    """Find potential near-duplicates by org, then fuzzy-match titles."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.organization == organization)
        .order_by(EventRecord.observed_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())
    return [
        c for c in candidates if is_near_duplicate(normalized_title, c.normalized_title, threshold)
    ]


async def batch_find_duplicates(
    session: AsyncSession,
    normalized_titles: list[str],
    organization: str,
) -> dict[str, EventRecord]:
    """Find existing events matching any of the given normalized titles for an org.

    Returns a dict mapping normalized_title to the first matching EventRecord.
    Single SELECT ... WHERE IN query for batch dedup lookups.
    """
    if not normalized_titles:
        return {}
    stmt = select(EventRecord).where(
        EventRecord.normalized_title.in_(normalized_titles),
        EventRecord.organization == organization,
    )
    result = await session.execute(stmt)
    found: dict[str, EventRecord] = {}
    for event in result.scalars().all():
        if event.normalized_title not in found:
            found[event.normalized_title] = event
    return found


async def is_duplicate(
    session: AsyncSession,
    normalized_title: str,
    organization: str,
    source_type: str,
    canonical_path: str,
    published_date: str | None,
    model_slug: str | None,
) -> EventRecord | None:
    """Check all dedup strategies. Returns the existing record if duplicate, else None."""
    # 1. Exact composite key (including model_slug)
    exact = await find_exact_duplicate(
        session,
        normalized_title,
        organization,
        source_type,
        canonical_path,
        published_date,
        model_slug,
    )
    if exact:
        return exact

    # 2. Model slug + org + date
    if model_slug:
        model_dup = await find_model_duplicate(session, model_slug, organization, published_date)
        if model_dup:
            return model_dup

    # 3. Fuzzy near-duplicate (same org)
    near_dups = await find_near_duplicates(session, normalized_title, organization)
    if near_dups:
        return near_dups[0]

    return None
