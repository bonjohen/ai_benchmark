"""Cross-reference table builder — links related EventRecords across sources.

Matching strategies:
- model_slug + time window (same model mentioned by different sources)
- organization + event_type (corroborating events)
- arxiv_id (research papers cited across sources)

Relationship types: confirms, supplements, conflicts_with, cites
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_, select

from ..models.events import CrossReference, EventRecord

# arXiv ID pattern: matches "arXiv:2312.12345" or "arXiv:2312.12345v2"
_ARXIV_ID_RE = re.compile(r"\barXiv:(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def find_related_by_model(
    session: AsyncSession,
    event: EventRecord,
    time_window_days: int = 7,
) -> list[EventRecord]:
    """Find events mentioning the same model within a time window."""
    if not event.model_slug:
        return []

    stmt = select(EventRecord).where(
        EventRecord.model_slug == event.model_slug,
        EventRecord.id != event.id,
    )
    # Filter by time window if we have an observed date
    if event.observed_at:
        window_start = event.observed_at - timedelta(days=time_window_days)
        window_end = event.observed_at + timedelta(days=time_window_days)
        stmt = stmt.where(EventRecord.observed_at.between(window_start, window_end))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_related_by_org_event_type(
    session: AsyncSession,
    event: EventRecord,
    time_window_days: int = 3,
) -> list[EventRecord]:
    """Find events from the same org with the same event type."""
    stmt = select(EventRecord).where(
        EventRecord.organization == event.organization,
        EventRecord.event_type == event.event_type,
        EventRecord.id != event.id,
    )
    if event.observed_at:
        window_start = event.observed_at - timedelta(days=time_window_days)
        window_end = event.observed_at + timedelta(days=time_window_days)
        stmt = stmt.where(EventRecord.observed_at.between(window_start, window_end))
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _extract_numbers(text: str | None) -> list[float]:
    """Extract numeric values from text for conflict comparison.

    Prioritizes percentage values (e.g. 95.0%) over bare numbers to
    avoid picking up model version numbers like the '5' in 'GPT-5'.
    """
    if not text:
        return []
    # First try percentage-like patterns
    pcts = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if pcts:
        return pcts
    # Fall back to dollar amounts or general numbers (skip single-digit after hyphen)
    return [float(m) for m in re.findall(r"(?<![-\w])(\d{2,}(?:\.\d+)?)", text)]


def _extract_arxiv_ids(text: str | None) -> set[str]:
    """Extract normalized arXiv IDs from text (strips version suffix for comparison)."""
    if not text:
        return set()
    ids = set()
    for match in _ARXIV_ID_RE.finditer(text):
        # Strip version suffix (v1, v2, …) for cross-version matching
        raw = match.group(1)
        ids.add(raw.split("v")[0])
    return ids


def determine_relationship(event_a: EventRecord, event_b: EventRecord) -> str:
    """Determine the relationship type between two events.

    Returns one of: confirms, supplements, conflicts_with, cites.
    """
    # Citation detection: one event's content references the other's arXiv ID
    ids_a = _extract_arxiv_ids(event_a.raw_content) | _extract_arxiv_ids(event_a.title)
    ids_b = _extract_arxiv_ids(event_b.raw_content) | _extract_arxiv_ids(event_b.title)
    if ids_a & ids_b:
        return "cites"

    # Conflict detection: same model + event type, different orgs, numerical disagreement >10%
    if (
        event_a.model_slug
        and event_a.model_slug == event_b.model_slug
        and event_a.event_type == event_b.event_type
        and event_a.organization != event_b.organization
    ):
        nums_a = _extract_numbers(event_a.raw_content)
        nums_b = _extract_numbers(event_b.raw_content)
        if nums_a and nums_b:
            # Compare first numerical values — if they differ by >10%, it's a conflict
            val_a, val_b = nums_a[0], nums_b[0]
            if val_a > 0 and abs(val_a - val_b) / val_a > 0.10:
                return "conflicts_with"

    # Same model from different source types → confirms
    if (
        event_a.model_slug
        and event_a.model_slug == event_b.model_slug
        and event_a.source_type != event_b.source_type
    ):
        return "confirms"

    # Same org, same event type, different paths → supplements
    if (
        event_a.organization == event_b.organization
        and event_a.event_type == event_b.event_type
        and event_a.canonical_path != event_b.canonical_path
    ):
        return "supplements"

    # Different orgs reporting on same model → supplements
    if (
        event_a.model_slug
        and event_a.model_slug == event_b.model_slug
        and event_a.organization != event_b.organization
    ):
        return "supplements"

    return "supplements"


async def xref_exists(
    session: AsyncSession,
    record_a_id: int,
    record_b_id: int,
) -> bool:
    """Check if a cross-reference already exists between two records (in either direction)."""
    stmt = (
        select(CrossReference)
        .where(
            or_(
                and_(
                    CrossReference.record_a_id == record_a_id,
                    CrossReference.record_b_id == record_b_id,
                ),
                and_(
                    CrossReference.record_a_id == record_b_id,
                    CrossReference.record_b_id == record_a_id,
                ),
            )
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def create_cross_reference(
    session: AsyncSession,
    event_a: EventRecord,
    event_b: EventRecord,
    relationship_type: str | None = None,
) -> CrossReference | None:
    """Create a cross-reference between two events if one doesn't already exist."""
    if await xref_exists(session, event_a.id, event_b.id):
        return None

    if relationship_type is None:
        relationship_type = determine_relationship(event_a, event_b)

    xref = CrossReference(
        record_a_id=event_a.id,
        record_b_id=event_b.id,
        relationship_type=relationship_type,
        created_at=datetime.now(UTC),
    )
    session.add(xref)
    await session.flush()
    return xref


async def find_related_by_arxiv_id(
    session: AsyncSession,
    event: EventRecord,
) -> list[EventRecord]:
    """Find events that share at least one arXiv ID with this event."""
    event_ids = _extract_arxiv_ids(event.raw_content) | _extract_arxiv_ids(event.title)
    if not event_ids:
        return []

    # Fetch recent events from any org and filter by shared arXiv ID in Python
    stmt = (
        select(EventRecord)
        .where(EventRecord.id != event.id)
        .order_by(EventRecord.observed_at.desc())
        .limit(100)
    )
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())
    related: list[EventRecord] = []
    for candidate in candidates:
        candidate_ids = _extract_arxiv_ids(candidate.raw_content) | _extract_arxiv_ids(
            candidate.title
        )
        if event_ids & candidate_ids:
            related.append(candidate)
    return related


async def build_cross_references(
    session: AsyncSession,
    event: EventRecord,
) -> list[CrossReference]:
    """Build all cross-references for a given event."""
    created: list[CrossReference] = []

    # Strategy 1: same model within time window
    model_related = await find_related_by_model(session, event)
    for related in model_related:
        xref = await create_cross_reference(session, event, related)
        if xref:
            created.append(xref)

    # Strategy 2: same org + event type within tight window
    org_related = await find_related_by_org_event_type(session, event)
    for related in org_related:
        xref = await create_cross_reference(session, event, related)
        if xref:
            created.append(xref)

    # Strategy 3: shared arXiv ID → cites relationship
    arxiv_related = await find_related_by_arxiv_id(session, event)
    for related in arxiv_related:
        xref = await create_cross_reference(session, event, related, relationship_type="cites")
        if xref:
            created.append(xref)

    return created
