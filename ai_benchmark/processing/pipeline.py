"""Post-collection processing pipeline: normalize → dedup → verify → cross-ref."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.events import EventRecord
from .cross_reference import build_cross_references
from .deduplicator import is_duplicate
from .normalizer import (
    classify_event_type,
    confidence_tier_for_classification,
    extract_date,
    extract_model_slug,
    normalize_title,
)
from .verification import create_claim, update_confirmation_status
from ..collection.snapshot import SnapshotManager
from ..sources.base import RawItem


async def process_item(
    session: AsyncSession,
    item: RawItem,
    source_id: int,
    page_id: int | None,
    organization: str,
    source_type: str,
    classification: str,
) -> EventRecord | None:
    """Run the full processing pipeline on a single raw item.

    Steps:
    1. Normalize fields (title, model slug, date, event type)
    2. Check for duplicates (composite key, model slug, fuzzy)
    3. Create EventRecord if not duplicate
    4. Create ClaimRecord with appropriate confidence tier
    5. Check confirmation status
    6. Build cross-references to related events

    Returns the new EventRecord, or None if duplicate.
    """
    # 1. Normalize
    norm_title = normalize_title(item.title)
    combined_text = f"{item.title} {item.body}"
    model_slug = item.model_hint or extract_model_slug(combined_text)
    published_date = extract_date(item.date_text or item.body)
    event_type = classify_event_type(item.title, item.body)

    # 2. Dedup
    existing = await is_duplicate(
        session,
        normalized_title=norm_title,
        organization=organization,
        source_type=source_type,
        canonical_path=item.url,
        published_date=published_date,
        model_slug=model_slug,
    )
    if existing:
        # Still create a claim for the existing event (multiple sources corroborate)
        confidence_tier = confidence_tier_for_classification(
            classification, organization=organization, source_type=source_type,
        )
        await create_claim(
            session,
            event=existing,
            claim_text=item.title,
            source_type=source_type,
            source_name=organization,
            confidence_tier=confidence_tier,
            page_title=item.page_title,
        )
        await update_confirmation_status(session, existing)
        return None

    # 3. Create event
    event = EventRecord(
        source_id=source_id,
        page_id=page_id,
        title=item.title,
        normalized_title=norm_title,
        organization=organization,
        source_type=source_type,
        canonical_path=item.url,
        published_date=published_date,
        event_type=event_type,
        model_slug=model_slug,
        benchmark_variant=item.metadata.get("benchmark_variant") or item.metadata.get("variant"),
        evaluation_conditions=item.metadata.get("evaluation_conditions") or item.metadata.get("conditions"),
        observed_at=datetime.now(timezone.utc),
        raw_content=item.body[:2000] if item.body else None,
    )
    session.add(event)
    await session.flush()

    # 4. Create initial claim
    confidence_tier = confidence_tier_for_classification(
        classification, organization=organization, source_type=source_type,
    )
    claim = await create_claim(
        session,
        event=event,
        claim_text=item.title,
        source_type=source_type,
        source_name=organization,
        confidence_tier=confidence_tier,
        page_title=item.page_title,
    )

    # 4b. Link pricing snapshot to claim
    if event_type == "pricing_change" and page_id is not None:
        snapshot_mgr = SnapshotManager(session)
        latest_snap = await snapshot_mgr.get_latest_snapshot(page_id)
        if latest_snap:
            claim.snapshot_id = latest_snap.id
            await session.flush()

    # 5. Check confirmation
    await update_confirmation_status(session, event)

    # 6. Cross-reference
    await build_cross_references(session, event)

    return event


async def process_items(
    session: AsyncSession,
    items: list[RawItem],
    source_id: int,
    page_id: int | None,
    organization: str,
    source_type: str,
    classification: str,
) -> list[EventRecord]:
    """Run the full processing pipeline on a batch of raw items."""
    created: list[EventRecord] = []
    for item in items:
        event = await process_item(
            session, item, source_id, page_id,
            organization, source_type, classification,
        )
        if event:
            created.append(event)
    return created
