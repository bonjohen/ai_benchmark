"""Model registry: curated model entities derived from event data."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from ...models.events import ClaimRecord, EventRecord
from ..models import ModelEntity, ModelEntitySlug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Organizations that create models vs. those that report on them.
_PUBLISHER_ORGS = frozenset(
    {
        "Anthropic",
        "OpenAI",
        "Google",
        "Google Gemini API / Google DeepMind",
        "Meta",
        "Meta Open Source AI",
        "xAI",
        "Mistral AI",
        "Cohere",
    }
)

# Date-suffix pattern for versioned API slugs (e.g., claude-3-5-sonnet-20241022).
_DATE_SUFFIX_RE = re.compile(r"-(\d{8})(-thinking-\d+k)?$")


def _prettify_slug(slug: str) -> str:
    """Convert a model slug to a human-readable display name."""
    return slug.replace("-", " ").replace("_", " ").title()


def _strip_date_suffix(slug: str) -> str | None:
    """Strip a -YYYYMMDD suffix from a slug. Returns base slug or None if no match."""
    m = _DATE_SUFFIX_RE.search(slug)
    if m:
        return slug[: m.start()]
    return None


def _is_publisher(org: str) -> bool:
    """Check if an organization is a model publisher."""
    return org in _PUBLISHER_ORGS


def _infer_status(event_types: set[str]) -> str:
    """Infer model status from its event types."""
    if "deprecation" in event_types:
        return "deprecated"
    if "model_release" in event_types or "api_update" in event_types:
        return "active"
    return "announced"


async def seed_model_entities(session: AsyncSession) -> dict[str, int]:
    """Populate model_entities and model_entity_slugs from event data.

    Returns stats dict with counts of entities created, slugs mapped, etc.
    """
    # Clear existing registry data for a clean reseed
    await session.execute(delete(ModelEntitySlug))
    await session.execute(delete(ModelEntity))
    await session.flush()

    # Load all distinct (model_slug, organization) pairs with event type info
    stmt = (
        select(
            EventRecord.model_slug,
            EventRecord.organization,
            func.group_concat(EventRecord.event_type.distinct()).label("event_types"),
            func.min(EventRecord.published_date).label("first_date"),
        )
        .where(EventRecord.model_slug.is_not(None))
        .group_by(EventRecord.model_slug, EventRecord.organization)
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Phase 1: Create entities from publisher-sourced slugs
    entities: dict[str, ModelEntity] = {}  # canonical_slug → entity
    slug_mappings: list[tuple[str, str, str]] = []  # (slug, org, canonical_slug)

    publisher_rows = [(r[0], r[1], r[2], r[3]) for r in rows if _is_publisher(r[1])]
    aggregator_rows = [(r[0], r[1], r[2], r[3]) for r in rows if not _is_publisher(r[1])]

    for slug, org, event_types_str, first_date in publisher_rows:
        event_types = set((event_types_str or "").split(","))
        canonical = slug
        status = _infer_status(event_types)

        if canonical not in entities:
            entities[canonical] = ModelEntity(
                canonical_slug=canonical,
                display_name=_prettify_slug(canonical),
                publisher=org,
                status=status,
                release_date=first_date,
            )
        slug_mappings.append((slug, org, canonical))

    # Phase 2: Map aggregator slugs to existing entities or create new ones
    for slug, org, event_types_str, first_date in aggregator_rows:
        # Try exact match
        if slug in entities:
            slug_mappings.append((slug, org, slug))
            continue

        # Try stripping date suffix
        base = _strip_date_suffix(slug)
        if base and base in entities:
            slug_mappings.append((slug, org, base))
            continue

        # No match — create a new entity with publisher="Unknown"
        if slug not in entities:
            event_types = set((event_types_str or "").split(","))
            entities[slug] = ModelEntity(
                canonical_slug=slug,
                display_name=_prettify_slug(slug),
                publisher="Unknown",
                status=_infer_status(event_types),
                release_date=first_date,
            )
        slug_mappings.append((slug, org, slug))

    # Phase 3: Persist entities
    for entity in entities.values():
        session.add(entity)
    await session.flush()

    # Phase 4: Persist slug mappings
    seen_slug_org: set[tuple[str, str]] = set()
    slugs_created = 0
    for slug, org, canonical in slug_mappings:
        key = (slug, org)
        if key in seen_slug_org:
            continue
        seen_slug_org.add(key)
        entity = entities[canonical]
        session.add(
            ModelEntitySlug(
                entity_id=entity.id,
                event_slug=slug,
                source_org=org,
            )
        )
        slugs_created += 1
    await session.flush()

    return {
        "entities_created": len(entities),
        "slugs_mapped": slugs_created,
        "publisher_sourced": len(publisher_rows),
        "aggregator_sourced": len(aggregator_rows),
    }


async def list_model_entities(
    session: AsyncSession,
    *,
    publisher: str | None = None,
    status: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[ModelEntity]:
    """Query curated model entities for the list page."""
    stmt = select(ModelEntity).order_by(ModelEntity.display_name).offset(offset).limit(limit)
    if publisher:
        stmt = stmt.where(ModelEntity.publisher == publisher)
    if status:
        stmt = stmt.where(ModelEntity.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_model_entity(session: AsyncSession, canonical_slug: str) -> ModelEntity | None:
    """Look up a single model entity by canonical slug."""
    stmt = select(ModelEntity).where(ModelEntity.canonical_slug == canonical_slug)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_entity_events(session: AsyncSession, entity_id: int) -> list[EventRecord]:
    """Get all events across all slug variants for a model entity."""
    # Get all mapped slugs
    slug_stmt = select(ModelEntitySlug.event_slug).where(ModelEntitySlug.entity_id == entity_id)
    slug_result = await session.execute(slug_stmt)
    slugs = [r[0] for r in slug_result.all()]

    if not slugs:
        return []

    event_stmt = (
        select(EventRecord)
        .where(EventRecord.model_slug.in_(slugs))
        .order_by(EventRecord.observed_at.desc())
    )
    result = await session.execute(event_stmt)
    return list(result.scalars().all())


async def get_entity_claims(session: AsyncSession, entity_id: int) -> list[ClaimRecord]:
    """Get all claims for events belonging to a model entity."""
    slug_stmt = select(ModelEntitySlug.event_slug).where(ModelEntitySlug.entity_id == entity_id)
    slug_result = await session.execute(slug_stmt)
    slugs = [r[0] for r in slug_result.all()]

    if not slugs:
        return []

    claim_stmt = (
        select(ClaimRecord)
        .join(EventRecord, ClaimRecord.event_id == EventRecord.id)
        .where(EventRecord.model_slug.in_(slugs))
        .order_by(ClaimRecord.observed_at.desc())
    )
    result = await session.execute(claim_stmt)
    return list(result.scalars().all())


async def count_model_entities(session: AsyncSession) -> int:
    """Count total curated model entities."""
    result = await session.execute(select(func.count(ModelEntity.id)))
    return result.scalar_one()


async def list_publishers(session: AsyncSession) -> list[str]:
    """Get distinct publisher names for filter dropdowns."""
    stmt = select(ModelEntity.publisher).distinct().order_by(ModelEntity.publisher)
    result = await session.execute(stmt)
    return [r[0] for r in result.all()]
