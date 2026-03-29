"""Query functions for events, claims, and cross-references."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ..models.events import ClaimRecord, CrossReference, EventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_events(
    session: AsyncSession,
    organization: str | None = None,
    event_type: str | None = None,
    model_slug: str | None = None,
    source_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EventRecord]:
    """Query events with optional filters."""
    stmt = select(EventRecord)

    if organization:
        stmt = stmt.where(EventRecord.organization == organization)
    if event_type:
        stmt = stmt.where(EventRecord.event_type == event_type)
    if model_slug:
        stmt = stmt.where(EventRecord.model_slug == model_slug)
    if source_type:
        stmt = stmt.where(EventRecord.source_type == source_type)
    if date_from:
        stmt = stmt.where(EventRecord.published_date >= date_from)
    if date_to:
        stmt = stmt.where(EventRecord.published_date <= date_to)

    stmt = stmt.order_by(EventRecord.observed_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_claims(
    session: AsyncSession,
    event_id: int | None = None,
    confidence_tier: str | None = None,
    confirmation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ClaimRecord]:
    """Query claims with optional filters."""
    stmt = select(ClaimRecord)

    if event_id is not None:
        stmt = stmt.where(ClaimRecord.event_id == event_id)
    if confidence_tier:
        stmt = stmt.where(ClaimRecord.confidence_tier == confidence_tier)
    if confirmation_status:
        stmt = stmt.where(ClaimRecord.confirmation_status == confirmation_status)

    stmt = stmt.order_by(ClaimRecord.observed_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_cross_refs(
    session: AsyncSession,
    event_id: int | None = None,
    relationship_type: str | None = None,
    limit: int = 50,
) -> list[CrossReference]:
    """Query cross-references for an event."""
    stmt = select(CrossReference)

    if event_id is not None:
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(
                CrossReference.record_a_id == event_id,
                CrossReference.record_b_id == event_id,
            )
        )
    if relationship_type:
        stmt = stmt.where(CrossReference.relationship_type == relationship_type)

    stmt = stmt.order_by(CrossReference.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_unconfirmed_claims(
    session: AsyncSession,
    limit: int = 50,
) -> list[ClaimRecord]:
    """Get claims that are still unconfirmed."""
    return await get_claims(session, confirmation_status="unconfirmed", limit=limit)


async def get_recent_changes(
    session: AsyncSession,
    hours: int = 24,
    limit: int = 100,
) -> list[EventRecord]:
    """Get events observed in the last N hours."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(EventRecord)
        .where(EventRecord.observed_at >= cutoff)
        .order_by(EventRecord.observed_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_events_by_org(session: AsyncSession) -> dict[str, int]:
    """Count events grouped by organization."""
    stmt = select(EventRecord.organization, func.count(EventRecord.id)).group_by(
        EventRecord.organization
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}


async def count_events_by_type(session: AsyncSession) -> dict[str, int]:
    """Count events grouped by event type."""
    stmt = select(EventRecord.event_type, func.count(EventRecord.id)).group_by(
        EventRecord.event_type
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}
