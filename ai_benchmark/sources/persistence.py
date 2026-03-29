"""Event record persistence — converts RawItems to EventRecords and stores them."""

from __future__ import annotations

from datetime import datetime, timezone, UTC

from sqlalchemy import select

from ..models.events import EventRecord
from ..processing.normalizer import (
    classify_event_type,
    extract_date,
    extract_model_slug,
    normalize_title,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from .base import RawItem


async def persist_events(
    session: AsyncSession,
    items: list[RawItem],
    source_id: int,
    page_id: int | None,
    organization: str,
    source_type: str,
) -> list[EventRecord]:
    """Convert RawItems to EventRecords and persist, skipping duplicates by composite key."""
    created: list[EventRecord] = []

    for item in items:
        norm_title = normalize_title(item.title)
        published = extract_date(item.date_text or item.body)
        model = item.model_hint or extract_model_slug(item.title + " " + item.body)
        event_type = classify_event_type(item.title, item.body)

        # Check for existing event by composite key
        existing = await session.execute(
            select(EventRecord)
            .where(
                EventRecord.normalized_title == norm_title,
                EventRecord.organization == organization,
                EventRecord.source_type == source_type,
                EventRecord.canonical_path == item.url,
            )
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        event = EventRecord(
            source_id=source_id,
            page_id=page_id,
            title=item.title,
            normalized_title=norm_title,
            organization=organization,
            source_type=source_type,
            canonical_path=item.url,
            published_date=published,
            event_type=event_type,
            model_slug=model,
            observed_at=datetime.now(UTC),
            raw_content=item.body[:2000] if item.body else None,
        )
        session.add(event)
        created.append(event)

    if created:
        await session.flush()
    return created
