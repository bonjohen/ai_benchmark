"""Anomaly detection: automated insight flagging and persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import ClaimRecord, EventRecord
from ..models import AnalysisInsight
from ..services.benchmark_trends import extract_benchmark_score

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def detect_anomalies(
    session: AsyncSession,
    *,
    window_days: int = 7,
) -> list[AnalysisInsight]:
    """Run all rules, persist new insights, return them."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    insights: list[AnalysisInsight] = []
    insights.extend(await _detect_new_orgs(session, cutoff))
    insights.extend(await _detect_rapid_iteration(session, cutoff))
    insights.extend(await _detect_benchmark_records(session, cutoff))
    insights.extend(await _detect_conflicts(session, cutoff))
    insights.extend(await _detect_price_drops(session, cutoff))
    insights.extend(await _detect_new_model_families(session, cutoff))

    # Persist new insights
    for insight in insights:
        session.add(insight)
    if insights:
        await session.flush()

    return insights


async def get_recent_insights(
    session: AsyncSession,
    *,
    limit: int = 20,
    severity: str | None = None,
    insight_type: str | None = None,
) -> list[AnalysisInsight]:
    """Query persisted insights with filters."""
    stmt = select(AnalysisInsight).order_by(AnalysisInsight.detected_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(AnalysisInsight.severity == severity)
    if insight_type:
        stmt = stmt.where(AnalysisInsight.insight_type == insight_type)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _already_exists(
    session: AsyncSession,
    insight_type: str,
    related_event_ids: str,
) -> bool:
    """Check if an insight already exists for these events."""
    stmt = (
        select(AnalysisInsight.id)
        .where(AnalysisInsight.insight_type == insight_type)
        .where(AnalysisInsight.related_event_ids == related_event_ids)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _detect_new_orgs(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """Org in recent events not in older events."""
    # Recent orgs
    recent_stmt = (
        select(EventRecord.organization).where(EventRecord.observed_at >= cutoff).distinct()
    )
    recent_result = await session.execute(recent_stmt)
    recent_orgs = {r[0] for r in recent_result.all()}

    # Historical orgs
    old_stmt = select(EventRecord.organization).where(EventRecord.observed_at < cutoff).distinct()
    old_result = await session.execute(old_stmt)
    old_orgs = {r[0] for r in old_result.all()}

    new_orgs = recent_orgs - old_orgs
    insights = []
    for org in new_orgs:
        event_ids_str = json.dumps([])
        if await _already_exists(session, "new_org", event_ids_str):
            continue
        insights.append(
            AnalysisInsight(
                insight_type="new_org",
                severity="notable",
                title=f"New organization: {org}",
                description=f"{org} appeared for the first time in the tracking window.",
                related_event_ids=event_ids_str,
                related_org=org,
            )
        )
    return insights


async def _detect_rapid_iteration(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """3+ events for same model_slug in window."""
    stmt = (
        select(
            EventRecord.model_slug,
            EventRecord.organization,
            func.count(EventRecord.id).label("cnt"),
        )
        .where(EventRecord.observed_at >= cutoff)
        .where(EventRecord.model_slug.is_not(None))
        .group_by(EventRecord.model_slug, EventRecord.organization)
    )
    result = await session.execute(stmt)

    insights = []
    for row in result.all():
        if row.cnt >= 3:
            event_ids_str = json.dumps([row.model_slug])
            if await _already_exists(session, "rapid_iteration", event_ids_str):
                continue
            insights.append(
                AnalysisInsight(
                    insight_type="rapid_iteration",
                    severity="info",
                    title=f"Rapid iteration: {row.model_slug}",
                    description=(
                        f"{row.model_slug} ({row.organization}) has "
                        f"{row.cnt} events in the last window."
                    ),
                    related_event_ids=event_ids_str,
                    related_model_slug=row.model_slug,
                    related_org=row.organization,
                )
            )
    return insights


async def _detect_benchmark_records(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """Score exceeds previous max for benchmark_variant."""
    # Recent benchmark events
    recent_stmt = (
        select(EventRecord)
        .where(EventRecord.observed_at >= cutoff)
        .where(EventRecord.benchmark_variant.is_not(None))
        .where(EventRecord.raw_content.is_not(None))
    )
    recent_result = await session.execute(recent_stmt)
    recent_events = list(recent_result.scalars().all())

    insights = []
    for event in recent_events:
        score = extract_benchmark_score(event.raw_content or "", event.benchmark_variant)
        if score is None:
            continue

        # Get previous max score for this benchmark
        prev_stmt = (
            select(EventRecord)
            .where(EventRecord.benchmark_variant == event.benchmark_variant)
            .where(EventRecord.observed_at < cutoff)
            .where(EventRecord.raw_content.is_not(None))
        )
        prev_result = await session.execute(prev_stmt)
        prev_events = list(prev_result.scalars().all())

        prev_max = None
        for prev in prev_events:
            prev_score = extract_benchmark_score(prev.raw_content or "", prev.benchmark_variant)
            if prev_score is not None and (prev_max is None or prev_score > prev_max):
                prev_max = prev_score

        if prev_max is not None and score > prev_max:
            event_ids_str = json.dumps([event.id])
            if await _already_exists(session, "benchmark_record", event_ids_str):
                continue
            insights.append(
                AnalysisInsight(
                    insight_type="benchmark_record",
                    severity="notable",
                    title=f"New record on {event.benchmark_variant}",
                    description=(
                        f"{event.model_slug or 'Unknown'} scored {score} on "
                        f"{event.benchmark_variant}, exceeding previous best of {prev_max}."
                    ),
                    related_event_ids=event_ids_str,
                    related_model_slug=event.model_slug,
                    related_org=event.organization,
                )
            )
    return insights


async def _detect_conflicts(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """Claims with confirmation_status='conflicted'."""
    stmt = (
        select(ClaimRecord)
        .where(ClaimRecord.confirmation_status == "conflicted")
        .where(ClaimRecord.observed_at >= cutoff)
    )
    result = await session.execute(stmt)
    claims = list(result.scalars().all())

    insights = []
    for claim in claims:
        event_ids_str = json.dumps([claim.event_id])
        if await _already_exists(session, "conflict_detected", event_ids_str):
            continue

        # Get the associated event for context
        event = await session.get(EventRecord, claim.event_id)
        insights.append(
            AnalysisInsight(
                insight_type="conflict_detected",
                severity="critical",
                title=f"Conflicting claim: {claim.claim_text[:80]}",
                description=(
                    f"Conflicting information detected from {claim.source_name} "
                    f"regarding event: {event.title if event else 'unknown'}."
                ),
                related_event_ids=event_ids_str,
                related_model_slug=event.model_slug if event else None,
                related_org=event.organization if event else None,
            )
        )
    return insights


async def _detect_price_drops(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """pricing_change events with decrease indicators in raw_content."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.event_type == "pricing_change")
        .where(EventRecord.observed_at >= cutoff)
        .where(EventRecord.raw_content.is_not(None))
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    decrease_keywords = ["drop", "decrease", "lower", "reduc", "cheap", "cut"]
    insights = []
    for event in events:
        content_lower = (event.raw_content or "").lower()
        if any(kw in content_lower for kw in decrease_keywords):
            event_ids_str = json.dumps([event.id])
            if await _already_exists(session, "price_drop", event_ids_str):
                continue
            insights.append(
                AnalysisInsight(
                    insight_type="price_drop",
                    severity="notable",
                    title=f"Price drop: {event.model_slug or event.organization}",
                    description=(
                        f"Pricing change for {event.model_slug or 'unknown'} "
                        f"({event.organization}) suggests a price decrease."
                    ),
                    related_event_ids=event_ids_str,
                    related_model_slug=event.model_slug,
                    related_org=event.organization,
                )
            )
    return insights


async def _detect_new_model_families(
    session: AsyncSession,
    cutoff: datetime,
) -> list[AnalysisInsight]:
    """First event for a model family prefix."""
    # Get all recent model slugs
    recent_stmt = (
        select(EventRecord.model_slug, EventRecord.organization)
        .where(EventRecord.observed_at >= cutoff)
        .where(EventRecord.model_slug.is_not(None))
        .distinct()
    )
    recent_result = await session.execute(recent_stmt)
    recent_models = list(recent_result.all())

    # Get all historical model slugs
    old_stmt = (
        select(EventRecord.model_slug)
        .where(EventRecord.observed_at < cutoff)
        .where(EventRecord.model_slug.is_not(None))
        .distinct()
    )
    old_result = await session.execute(old_stmt)
    old_slugs = {r[0] for r in old_result.all()}

    # Extract family prefixes (everything before the last dash-number segment)
    def family_prefix(slug: str) -> str:
        parts = slug.rsplit("-", 1)
        if len(parts) == 2 and parts[1].replace(".", "").isdigit():
            return parts[0]
        return slug

    old_families = {family_prefix(s) for s in old_slugs}

    insights = []
    seen_families: set[str] = set()
    for row in recent_models:
        slug = row.model_slug
        prefix = family_prefix(slug)
        if prefix not in old_families and prefix not in seen_families:
            seen_families.add(prefix)
            event_ids_str = json.dumps([slug])
            if await _already_exists(session, "new_model", event_ids_str):
                continue
            insights.append(
                AnalysisInsight(
                    insight_type="new_model",
                    severity="info",
                    title=f"New model family: {prefix}",
                    description=(
                        f"First appearance of model family '{prefix}' from {row.organization}."
                    ),
                    related_event_ids=event_ids_str,
                    related_model_slug=slug,
                    related_org=row.organization,
                )
            )
    return insights
