"""Model lifecycle analysis: profiles, timelines, and comparisons."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from sqlalchemy import case, func, select

from ...models.events import ClaimRecord, CrossReference, EventRecord
from ..types import (
    BenchmarkDataPoint,
    ModelComparisonMatrix,
    ModelProfile,
    ModelSummary,
    TimelineEntry,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _infer_status(event_types: list[str]) -> str:
    """Infer model status from its event types."""
    if any(t == "deprecation" for t in event_types):
        return "deprecated"
    if len(event_types) == 1 and event_types[0] == "announcement":
        return "announced"
    return "active"


async def list_tracked_models(
    session: AsyncSession,
    *,
    organization: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ModelSummary]:
    """All distinct model_slugs with event counts and date ranges."""
    # Use published_date when available, fall back to observed_at formatted as date
    effective_date = case(
        (
            EventRecord.published_date.is_not(None),
            EventRecord.published_date,
        ),
        else_=func.strftime("%Y-%m-%d", EventRecord.observed_at),
    )
    stmt = (
        select(
            EventRecord.model_slug,
            EventRecord.organization,
            func.min(effective_date).label("first_seen"),
            func.max(effective_date).label("latest_activity"),
            func.count(EventRecord.id).label("event_count"),
        )
        .where(EventRecord.model_slug.is_not(None))
        .group_by(EventRecord.model_slug, EventRecord.organization)
        .order_by(func.max(EventRecord.observed_at).desc())
        .offset(offset)
        .limit(limit)
    )
    if organization:
        stmt = stmt.where(EventRecord.organization == organization)

    result = await session.execute(stmt)
    rows = result.all()

    summaries = []
    for row in rows:
        # Fetch event types for status inference
        type_stmt = (
            select(EventRecord.event_type)
            .where(EventRecord.model_slug == row.model_slug)
            .distinct()
        )
        type_result = await session.execute(type_stmt)
        event_types = [r[0] for r in type_result.all()]

        summaries.append(
            ModelSummary(
                model_slug=row.model_slug,
                organization=row.organization,
                first_seen=row.first_seen,
                latest_activity=row.latest_activity,
                event_count=row.event_count,
                status=_infer_status(event_types),
            )
        )
    return summaries


async def get_model_timeline(
    session: AsyncSession,
    model_slug: str,
) -> list[TimelineEntry]:
    """Ordered event timeline for a model."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.model_slug == model_slug)
        .order_by(EventRecord.observed_at.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    entries = []
    for event in events:
        # Get the highest-confidence claim for this event
        claim_stmt = (
            select(ClaimRecord)
            .where(ClaimRecord.event_id == event.id)
            .order_by(ClaimRecord.observed_at.asc())
            .limit(1)
        )
        claim_result = await session.execute(claim_stmt)
        claim = claim_result.scalar_one_or_none()

        entries.append(
            TimelineEntry(
                date=event.published_date or event.observed_at.strftime("%Y-%m-%d"),
                event_type=event.event_type,
                title=event.title,
                confidence_tier=claim.confidence_tier if claim else "unknown",
                confirmation_status=claim.confirmation_status if claim else "unconfirmed",
                event_id=event.id,
            )
        )
    return entries


async def build_model_profile(
    session: AsyncSession,
    model_slug: str,
) -> ModelProfile | None:
    """Complete lifecycle for one model. Returns None if slug not found."""
    # Fetch all events for this model
    stmt = (
        select(EventRecord)
        .where(EventRecord.model_slug == model_slug)
        .order_by(EventRecord.observed_at.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return None

    organization = events[0].organization
    event_types = [e.event_type for e in events]
    published_dates = [e.published_date or e.observed_at.strftime("%Y-%m-%d") for e in events]

    # Build timeline
    milestones = await get_model_timeline(session, model_slug)

    # Claim summary
    event_ids = [e.id for e in events]
    claim_stmt = select(ClaimRecord).where(ClaimRecord.event_id.in_(event_ids))
    claim_result = await session.execute(claim_stmt)
    claims = list(claim_result.scalars().all())

    claim_summary: dict[str, int] = defaultdict(int)
    for claim in claims:
        claim_summary[claim.confirmation_status] += 1

    # Benchmark scores
    benchmark_scores = []
    for event in events:
        if event.benchmark_variant and event.raw_content:
            benchmark_scores.append(
                BenchmarkDataPoint(
                    model_slug=model_slug,
                    score=None,  # Score extraction deferred to benchmark_trends service
                    date=event.published_date or event.observed_at.strftime("%Y-%m-%d"),
                    source_name=event.organization,
                    benchmark_variant=event.benchmark_variant,
                )
            )

    # Related models via cross-references
    related_slugs: set[str] = set()
    for event in events:
        xref_stmt = select(CrossReference).where(
            (CrossReference.record_a_id == event.id) | (CrossReference.record_b_id == event.id)
        )
        xref_result = await session.execute(xref_stmt)
        for xref in xref_result.scalars().all():
            other_id = xref.record_b_id if xref.record_a_id == event.id else xref.record_a_id
            other_event = await session.get(EventRecord, other_id)
            if other_event and other_event.model_slug and other_event.model_slug != model_slug:
                related_slugs.add(other_event.model_slug)

    return ModelProfile(
        model_slug=model_slug,
        organization=organization,
        first_seen=min(published_dates) if published_dates else None,
        latest_activity=max(published_dates) if published_dates else None,
        status=_infer_status(event_types),
        milestones=milestones,
        claim_summary=dict(claim_summary),
        benchmark_scores=benchmark_scores,
        related_models=sorted(related_slugs),
    )


async def compare_models(
    session: AsyncSession,
    model_slugs: list[str],
) -> ModelComparisonMatrix:
    """Side-by-side comparison of multiple models."""
    profiles: dict[str, ModelProfile] = {}
    for slug in model_slugs:
        profile = await build_model_profile(session, slug)
        if profile:
            profiles[slug] = profile
    return ModelComparisonMatrix(model_slugs=model_slugs, profiles=profiles)
