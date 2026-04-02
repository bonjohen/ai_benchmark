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
class ClaimDetail:
    """A unique claim from a specific source."""

    text: str
    source_name: str
    confidence_tier: str
    confirmation_status: str


@dataclass
class CrossRefDetail:
    """A cross-reference linking two events."""

    relationship_type: str
    other_title: str
    other_org: str


@dataclass
class Article:
    """A publication-style event with deduplicated claims."""

    title: str
    published_date: str | None
    publisher: str  # organization
    source_type: str
    event_type: str
    model_slug: str | None
    claims: list[ClaimDetail] = field(default_factory=list)
    cross_refs: list[CrossRefDetail] = field(default_factory=list)
    event_id: int = 0


@dataclass
class OrgActivity:
    organization: str
    event_count: int
    by_type: dict[str, int] = field(default_factory=dict)


@dataclass
class DailyReport:
    generated_at: datetime
    yesterday: list[Article]
    last_7_days: list[Article]  # includes yesterday
    weekly_stats: WeeklyStats


@dataclass
class WeeklyStats:
    total_events: int
    total_unique_claims: int
    by_org: list[OrgActivity]
    by_type: dict[str, int]
    model_activity: dict[str, int]
    confirmed_count: int
    conflicted_count: int


# ─── Helpers ───


def _build_article(event: EventRecord) -> Article:
    """Convert an EventRecord with loaded claims into a deduplicated Article."""
    # Deduplicate claims by (text, source_name) — keep unique perspectives only
    seen: set[tuple[str, str]] = set()
    unique_claims: list[ClaimDetail] = []
    for c in event.claims:
        key = (c.claim_text, c.source_name)
        if key not in seen:
            seen.add(key)
            unique_claims.append(
                ClaimDetail(
                    text=c.claim_text,
                    source_name=c.source_name,
                    confidence_tier=c.confidence_tier,
                    confirmation_status=c.confirmation_status,
                )
            )

    return Article(
        title=event.title,
        published_date=event.published_date,
        publisher=event.organization,
        source_type=event.source_type,
        event_type=event.event_type,
        model_slug=event.model_slug,
        claims=unique_claims,
        event_id=event.id,
    )


async def _attach_cross_refs(
    session: AsyncSession,
    articles: list[Article],
) -> None:
    """Batch-fetch cross-references and attach to articles."""
    event_ids = [a.event_id for a in articles]
    if not event_ids:
        return

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
            ),
            CrossReference.relationship_type.in_(["confirms", "conflicts_with"]),
        )
    )
    result = await session.execute(stmt)

    id_set = set(event_ids)
    refs: dict[int, list[CrossRefDetail]] = {}
    for a_id, b_id, rel_type, title_a, org_a, title_b, org_b in result.all():
        if a_id in id_set:
            refs.setdefault(a_id, []).append(
                CrossRefDetail(relationship_type=rel_type, other_title=title_b, other_org=org_b)
            )
        if b_id in id_set:
            refs.setdefault(b_id, []).append(
                CrossRefDetail(relationship_type=rel_type, other_title=title_a, other_org=org_a)
            )

    for a in articles:
        a.cross_refs = refs.get(a.event_id, [])


def _date_for_event(event: EventRecord) -> str | None:
    """Return the effective date for filtering: published_date if valid, else observed_at date."""
    if event.published_date and len(event.published_date) >= 10:
        return event.published_date[:10]
    return event.observed_at.strftime("%Y-%m-%d")


# ─── Queries ───


async def _fetch_events_in_date_range(
    session: AsyncSession,
    date_from: str,
    date_to: str,
) -> list[Article]:
    """Fetch events with a published_date in [date_from, date_to].

    Only includes events that have an explicit published_date. Events without
    one (leaderboard rows, page chrome, documentation fragments) are excluded
    since they cannot be reliably placed in time.
    """
    stmt = (
        select(EventRecord)
        .options(selectinload(EventRecord.claims))
        .where(
            EventRecord.published_date.isnot(None),
            EventRecord.published_date >= date_from,
            EventRecord.published_date <= date_to,
        )
        .order_by(EventRecord.published_date.desc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().unique().all())

    articles = [_build_article(e) for e in events]

    # Filter out noise: skip articles with very short titles
    articles = [a for a in articles if len(a.title.strip()) > 10]

    return articles


async def _gather_weekly_stats(
    session: AsyncSession,
    date_from: str,
    date_to: str,
) -> WeeklyStats:
    """Compute summary statistics for events with published_date in range."""
    date_filter = EventRecord.published_date.between(date_from, date_to)

    # Events by org and type
    stmt = (
        select(
            EventRecord.organization,
            EventRecord.event_type,
            func.count(EventRecord.id),
        )
        .where(date_filter)
        .group_by(EventRecord.organization, EventRecord.event_type)
    )
    result = await session.execute(stmt)

    org_map: dict[str, OrgActivity] = {}
    by_type: dict[str, int] = {}
    for org, etype, cnt in result.all():
        if org not in org_map:
            org_map[org] = OrgActivity(organization=org, event_count=0)
        org_map[org].event_count += cnt
        org_map[org].by_type[etype] = org_map[org].by_type.get(etype, 0) + cnt
        by_type[etype] = by_type.get(etype, 0) + cnt

    by_org = sorted(org_map.values(), key=lambda o: o.event_count, reverse=True)
    total_events = sum(o.event_count for o in by_org)

    # Unique claims count
    stmt_claims = (
        select(func.count(func.distinct(ClaimRecord.claim_text)))
        .join(EventRecord)
        .where(date_filter)
    )
    result = await session.execute(stmt_claims)
    total_unique_claims = result.scalar() or 0

    # Model activity
    stmt_models = (
        select(EventRecord.model_slug, func.count(EventRecord.id))
        .where(
            EventRecord.model_slug.isnot(None),
            EventRecord.model_slug != "",
            date_filter,
        )
        .group_by(EventRecord.model_slug)
        .order_by(func.count(EventRecord.id).desc())
        .limit(20)
    )
    result = await session.execute(stmt_models)
    model_activity = {row[0]: row[1] for row in result.all()}

    # Confirmed/conflicted counts
    stmt_confirmed = (
        select(func.count(func.distinct(ClaimRecord.event_id)))
        .join(EventRecord)
        .where(ClaimRecord.confirmation_status == "confirmed", date_filter)
    )
    result = await session.execute(stmt_confirmed)
    confirmed_count = result.scalar() or 0

    stmt_conflicted = (
        select(func.count(func.distinct(ClaimRecord.event_id)))
        .join(EventRecord)
        .where(ClaimRecord.confirmation_status == "conflicted", date_filter)
    )
    result = await session.execute(stmt_conflicted)
    conflicted_count = result.scalar() or 0

    return WeeklyStats(
        total_events=total_events,
        total_unique_claims=total_unique_claims,
        by_org=by_org,
        by_type=by_type,
        model_activity=model_activity,
        confirmed_count=confirmed_count,
        conflicted_count=conflicted_count,
    )


# ─── Public API ───


async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
    days: int = 7,
) -> DailyReport:
    """Assemble the full daily report filtered by published_date."""
    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    yesterday_dt = now - timedelta(days=1)
    yesterday = yesterday_dt.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    yesterday_articles = await _fetch_events_in_date_range(session, yesterday, today)
    await _attach_cross_refs(session, yesterday_articles)

    weekly_articles = await _fetch_events_in_date_range(session, week_ago, today)
    await _attach_cross_refs(session, weekly_articles)

    weekly_stats = await _gather_weekly_stats(session, week_ago, today)

    return DailyReport(
        generated_at=now,
        yesterday=yesterday_articles,
        last_7_days=weekly_articles,
        weekly_stats=weekly_stats,
    )
