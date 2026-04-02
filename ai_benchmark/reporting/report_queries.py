"""Data assembly queries for the daily intelligence report."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased, selectinload

from ..models.events import ClaimRecord, CrossReference, EventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ─── Data structures ───


@dataclass
class ClaimSummary:
    claim_text: str
    source_name: str
    confidence_tier: str
    confirmation_status: str
    observed_at: datetime


@dataclass
class CrossRefSummary:
    relationship_type: str
    other_event_title: str
    other_event_org: str


@dataclass
class EventDetail:
    event_id: int
    title: str
    organization: str
    event_type: str
    model_slug: str | None
    published_date: str | None
    observed_at: datetime
    source_type: str
    claims: list[ClaimSummary] = field(default_factory=list)
    cross_refs: list[CrossRefSummary] = field(default_factory=list)


@dataclass
class OrgActivity:
    organization: str
    event_count: int
    by_type: dict[str, int] = field(default_factory=dict)


@dataclass
class RecentChangesReport:
    generated_at: datetime
    window_hours: int
    events: list[EventDetail]
    total_count: int


@dataclass
class WeeklySummaryReport:
    generated_at: datetime
    window_days: int
    total_events: int
    total_claims: int
    by_org: list[OrgActivity]
    by_type: dict[str, int]
    confirmed_events: list[EventDetail]
    conflicted_events: list[EventDetail]
    model_activity: dict[str, int]
    notable_cross_refs: list[CrossRefSummary]


@dataclass
class DailyReport:
    recent_changes: RecentChangesReport
    weekly_summary: WeeklySummaryReport


# ─── Priority ordering for event types ───

_EVENT_TYPE_PRIORITY = {
    "model_release": 0,
    "pricing_change": 1,
    "benchmark_result": 2,
    "api_update": 3,
    "deprecation": 4,
    "system_card": 5,
    "announcement": 6,
}


def _event_sort_key(e: EventDetail) -> tuple[int, datetime]:
    return (_EVENT_TYPE_PRIORITY.get(e.event_type, 99), e.observed_at)


# ─── Helpers ───


def _event_to_detail(event: EventRecord) -> EventDetail:
    claims = [
        ClaimSummary(
            claim_text=c.claim_text,
            source_name=c.source_name,
            confidence_tier=c.confidence_tier,
            confirmation_status=c.confirmation_status,
            observed_at=c.observed_at,
        )
        for c in event.claims
    ]
    return EventDetail(
        event_id=event.id,
        title=event.title,
        organization=event.organization,
        event_type=event.event_type,
        model_slug=event.model_slug,
        published_date=event.published_date,
        observed_at=event.observed_at,
        source_type=event.source_type,
        claims=claims,
    )


async def _batch_cross_refs(
    session: AsyncSession,
    event_ids: list[int],
) -> dict[int, list[CrossRefSummary]]:
    """Fetch cross-references for a batch of event IDs, resolved with event titles."""
    if not event_ids:
        return {}

    event_a = aliased(EventRecord)
    event_b = aliased(EventRecord)

    stmt = (
        select(
            CrossReference.record_a_id,
            CrossReference.record_b_id,
            CrossReference.relationship_type,
            event_a.title.label("title_a"),
            event_a.organization.label("org_a"),
            event_b.title.label("title_b"),
            event_b.organization.label("org_b"),
        )
        .join(event_a, CrossReference.record_a_id == event_a.id)
        .join(event_b, CrossReference.record_b_id == event_b.id)
        .where(
            or_(
                CrossReference.record_a_id.in_(event_ids),
                CrossReference.record_b_id.in_(event_ids),
            )
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    id_set = set(event_ids)
    refs: dict[int, list[CrossRefSummary]] = {}
    for row in rows:
        a_id, b_id, rel_type, title_a, org_a, title_b, org_b = row
        # For each event in our set, show the "other" event
        if a_id in id_set:
            refs.setdefault(a_id, []).append(
                CrossRefSummary(
                    relationship_type=rel_type,
                    other_event_title=title_b,
                    other_event_org=org_b,
                )
            )
        if b_id in id_set:
            refs.setdefault(b_id, []).append(
                CrossRefSummary(
                    relationship_type=rel_type,
                    other_event_title=title_a,
                    other_event_org=org_a,
                )
            )
    return refs


# ─── Part 1: Recent changes ───


async def gather_recent_changes(
    session: AsyncSession,
    hours: int = 24,
) -> RecentChangesReport:
    """Gather events with claims from the last N hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    stmt = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .where(EventRecord.observed_at >= cutoff)
        .order_by(EventRecord.observed_at.desc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().unique().all())

    details = [_event_to_detail(e) for e in events]
    event_ids = [d.event_id for d in details]

    xrefs = await _batch_cross_refs(session, event_ids)
    for d in details:
        d.cross_refs = xrefs.get(d.event_id, [])

    details.sort(key=_event_sort_key)

    return RecentChangesReport(
        generated_at=datetime.now(UTC),
        window_hours=hours,
        events=details,
        total_count=len(details),
    )


# ─── Part 2: Weekly summary ───


async def gather_weekly_summary(
    session: AsyncSession,
    days: int = 7,
) -> WeeklySummaryReport:
    """Gather aggregated summary for the last N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Events by org and type
    stmt_org_type = (
        select(
            EventRecord.organization,
            EventRecord.event_type,
            func.count(EventRecord.id),
        )
        .where(EventRecord.observed_at >= cutoff)
        .group_by(EventRecord.organization, EventRecord.event_type)
    )
    result = await session.execute(stmt_org_type)
    org_type_rows = result.all()

    org_map: dict[str, OrgActivity] = {}
    by_type: dict[str, int] = {}
    for org, etype, cnt in org_type_rows:
        if org not in org_map:
            org_map[org] = OrgActivity(organization=org, event_count=0)
        org_map[org].event_count += cnt
        org_map[org].by_type[etype] = org_map[org].by_type.get(etype, 0) + cnt
        by_type[etype] = by_type.get(etype, 0) + cnt

    by_org = sorted(org_map.values(), key=lambda o: o.event_count, reverse=True)
    total_events = sum(o.event_count for o in by_org)

    # Total claims in window
    stmt_claims = select(func.count(ClaimRecord.id)).where(ClaimRecord.observed_at >= cutoff)
    result = await session.execute(stmt_claims)
    total_claims = result.scalar() or 0

    # Confirmed events (events that have at least one confirmed claim)
    stmt_confirmed = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .join(ClaimRecord)
        .where(
            EventRecord.observed_at >= cutoff,
            ClaimRecord.confirmation_status == "confirmed",
        )
        .distinct()
    )
    result = await session.execute(stmt_confirmed)
    confirmed = [_event_to_detail(e) for e in result.scalars().unique().all()]

    # Conflicted events
    stmt_conflicted = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .join(ClaimRecord)
        .where(
            EventRecord.observed_at >= cutoff,
            ClaimRecord.confirmation_status == "conflicted",
        )
        .distinct()
    )
    result = await session.execute(stmt_conflicted)
    conflicted = [_event_to_detail(e) for e in result.scalars().unique().all()]

    # Model activity (claims per model slug)
    stmt_models = (
        select(EventRecord.model_slug, func.count(ClaimRecord.id))
        .join(ClaimRecord)
        .where(
            EventRecord.observed_at >= cutoff,
            EventRecord.model_slug.isnot(None),
            EventRecord.model_slug != "",
        )
        .group_by(EventRecord.model_slug)
        .order_by(func.count(ClaimRecord.id).desc())
        .limit(20)
    )
    result = await session.execute(stmt_models)
    model_activity = {row[0]: row[1] for row in result.all()}

    # Notable cross-references (confirms and conflicts_with)
    event_a = aliased(EventRecord)
    event_b = aliased(EventRecord)
    stmt_xrefs = (
        select(
            CrossReference.relationship_type,
            event_a.title.label("title_a"),
            event_a.organization.label("org_a"),
            event_b.title.label("title_b"),
            event_b.organization.label("org_b"),
        )
        .join(event_a, CrossReference.record_a_id == event_a.id)
        .join(event_b, CrossReference.record_b_id == event_b.id)
        .where(
            CrossReference.created_at >= cutoff,
            CrossReference.relationship_type.in_(["confirms", "conflicts_with"]),
        )
        .order_by(CrossReference.created_at.desc())
        .limit(20)
    )
    result = await session.execute(stmt_xrefs)
    notable_xrefs = [
        CrossRefSummary(
            relationship_type=row[0],
            other_event_title=f"{row[1]} ({row[2]}) -> {row[3]} ({row[4]})",
            other_event_org="",
        )
        for row in result.all()
    ]

    return WeeklySummaryReport(
        generated_at=datetime.now(UTC),
        window_days=days,
        total_events=total_events,
        total_claims=total_claims,
        by_org=by_org,
        by_type=by_type,
        confirmed_events=confirmed,
        conflicted_events=conflicted,
        model_activity=model_activity,
        notable_cross_refs=notable_xrefs,
    )


# ─── Orchestrator ───


async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
    days: int = 7,
) -> DailyReport:
    """Assemble the full daily report."""
    recent = await gather_recent_changes(session, hours=hours)
    weekly = await gather_weekly_summary(session, days=days)
    return DailyReport(recent_changes=recent, weekly_summary=weekly)
