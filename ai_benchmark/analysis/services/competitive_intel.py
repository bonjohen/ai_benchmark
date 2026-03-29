"""Competitive intelligence: cross-org activity timelines and cluster detection."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from ...models.events import EventRecord
from ..types import ActivityTimeline, CompetitiveCluster, OrgActivity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_activity_timeline(
    session: AsyncSession,
    *,
    window_days: int = 30,
    organizations: list[str] | None = None,
) -> ActivityTimeline:
    """Cross-org activity for a time window."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    stmt = (
        select(EventRecord)
        .where(EventRecord.observed_at >= cutoff)
        .order_by(EventRecord.observed_at.asc())
    )
    if organizations:
        stmt = stmt.where(EventRecord.organization.in_(organizations))

    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Build per-org summaries
    org_data: dict[str, dict] = defaultdict(
        lambda: {"event_counts": defaultdict(int), "models": set(), "total": 0}
    )
    for event in events:
        org = event.organization
        org_data[org]["event_counts"][event.event_type] += 1
        if event.model_slug:
            org_data[org]["models"].add(event.model_slug)
        org_data[org]["total"] += 1

    org_activities = []
    for org_name in sorted(org_data, key=lambda o: -org_data[o]["total"]):
        data = org_data[org_name]
        org_activities.append(
            OrgActivity(
                organization=org_name,
                event_counts=dict(data["event_counts"]),
                active_models=sorted(data["models"]),
                total_events=data["total"],
            )
        )

    # Detect clusters
    clusters = await detect_competitive_clusters(session, window_days=window_days)

    window_start = cutoff.strftime("%Y-%m-%d")
    window_end = datetime.now(UTC).strftime("%Y-%m-%d")

    return ActivityTimeline(
        window_start=window_start,
        window_end=window_end,
        org_activities=org_activities,
        clusters=clusters,
    )


async def detect_competitive_clusters(
    session: AsyncSession,
    *,
    window_days: int = 7,
    min_orgs: int = 2,
) -> list[CompetitiveCluster]:
    """Find time windows where 2+ orgs had similar event types."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    stmt = (
        select(EventRecord)
        .where(EventRecord.observed_at >= cutoff)
        .order_by(EventRecord.observed_at.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Group by (event_type, iso_week) -> {org: [event_ids]}
    week_buckets: dict[tuple[str, int, int], dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    week_dates: dict[tuple[str, int, int], list[str]] = defaultdict(list)

    for event in events:
        iso = event.observed_at.isocalendar()
        key = (event.event_type, iso[0], iso[1])  # (type, year, week)
        week_buckets[key][event.organization].append(event.id)
        date_str = event.published_date or event.observed_at.strftime("%Y-%m-%d")
        week_dates[key].append(date_str)

    clusters = []
    for (event_type, _year, _week), org_events in week_buckets.items():
        if len(org_events) >= min_orgs:
            all_ids = []
            for ids in org_events.values():
                all_ids.extend(ids)
            dates = sorted(week_dates[(event_type, _year, _week)])
            clusters.append(
                CompetitiveCluster(
                    start_date=dates[0] if dates else "",
                    end_date=dates[-1] if dates else "",
                    event_type=event_type,
                    organizations=sorted(org_events.keys()),
                    event_count=len(all_ids),
                    event_ids=all_ids,
                )
            )

    return clusters


async def org_activity_summary(
    session: AsyncSession,
    organization: str,
    *,
    window_days: int = 90,
) -> OrgActivity:
    """Per-org activity summary."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    stmt = (
        select(EventRecord)
        .where(EventRecord.organization == organization)
        .where(EventRecord.observed_at >= cutoff)
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    event_counts: dict[str, int] = defaultdict(int)
    models: set[str] = set()
    for event in events:
        event_counts[event.event_type] += 1
        if event.model_slug:
            models.add(event.model_slug)

    return OrgActivity(
        organization=organization,
        event_counts=dict(event_counts),
        active_models=sorted(models),
        total_events=len(events),
    )
