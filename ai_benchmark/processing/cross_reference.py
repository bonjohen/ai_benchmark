"""Cross-reference table builder — links related EventRecords across sources.

Matching strategies:
- model_slug + time window (same model mentioned by different sources)
- organization + event_type (corroborating events)
- arxiv_id (research papers cited across sources)

Relationship types: confirms, supplements, conflicts_with, cites
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.events import CrossReference, EventRecord


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
        stmt = stmt.where(
            EventRecord.observed_at.between(window_start, window_end)
        )
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
        stmt = stmt.where(
            EventRecord.observed_at.between(window_start, window_end)
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def determine_relationship(event_a: EventRecord, event_b: EventRecord) -> str:
    """Determine the relationship type between two events."""
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
    stmt = select(CrossReference).where(
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
    ).limit(1)
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
        created_at=datetime.now(timezone.utc),
    )
    session.add(xref)
    await session.flush()
    return xref


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

    return created
