"""Research pulse: citation trends, topic clustering, paper-to-product links."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import EventRecord
from ...models.research import CandidatePaper, EnrichedPaper
from ..types import PaperCitationEntry, PaperProductLink, ResearchTrends

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_research_trends(
    session: AsyncSession,
    *,
    window_days: int = 90,
) -> ResearchTrends:
    """Trending topics, citation leaders, paper-to-product lag."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    # Paper counts by status
    total_stmt = select(func.count(CandidatePaper.id)).where(CandidatePaper.discovered_at >= cutoff)
    promoted_stmt = select(func.count(CandidatePaper.id)).where(
        CandidatePaper.discovered_at >= cutoff,
        CandidatePaper.status == "promoted",
    )
    rejected_stmt = select(func.count(CandidatePaper.id)).where(
        CandidatePaper.discovered_at >= cutoff,
        CandidatePaper.status == "rejected",
    )
    pending_stmt = select(func.count(CandidatePaper.id)).where(
        CandidatePaper.discovered_at >= cutoff,
        CandidatePaper.status == "pending",
    )

    total = (await session.execute(total_stmt)).scalar() or 0
    promoted = (await session.execute(promoted_stmt)).scalar() or 0
    rejected = (await session.execute(rejected_stmt)).scalar() or 0
    pending = (await session.execute(pending_stmt)).scalar() or 0

    # Citation leaders
    citation_leaders = await get_citation_leaders(session, limit=20)

    # Topic counts from relevance_tags
    topic_counts = await _count_topics(session, cutoff)

    # Paper-to-product links
    paper_product_links = await detect_paper_to_product(session, max_lag_days=window_days)

    return ResearchTrends(
        window_days=window_days,
        total_papers=total,
        promoted_count=promoted,
        rejected_count=rejected,
        pending_count=pending,
        citation_leaders=citation_leaders,
        topic_counts=topic_counts,
        paper_product_links=paper_product_links,
    )


async def get_citation_leaders(
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[PaperCitationEntry]:
    """Top papers by citation count."""
    stmt = select(EnrichedPaper).order_by(EnrichedPaper.citation_count.desc()).limit(limit)
    result = await session.execute(stmt)
    papers = list(result.scalars().all())

    return [
        PaperCitationEntry(
            title=p.title,
            arxiv_id=p.arxiv_id,
            citation_count=p.citation_count,
            venue=p.venue,
            enriched_at=p.enriched_at.strftime("%Y-%m-%d") if p.enriched_at else "",
        )
        for p in papers
    ]


async def detect_paper_to_product(
    session: AsyncSession,
    *,
    max_lag_days: int = 180,
) -> list[PaperProductLink]:
    """Match enriched papers to model_release events by org + time."""
    # Get all tracked organizations
    org_stmt = select(EventRecord.organization).distinct()
    org_result = await session.execute(org_stmt)
    tracked_orgs = [r[0] for r in org_result.all()]

    if not tracked_orgs:
        return []

    # Get all enriched papers
    paper_stmt = select(EnrichedPaper).where(EnrichedPaper.authors.is_not(None))
    paper_result = await session.execute(paper_stmt)
    papers = list(paper_result.scalars().all())

    links = []
    for paper in papers:
        if not paper.authors:
            continue

        authors_lower = paper.authors.lower()

        for org in tracked_orgs:
            if org.lower() not in authors_lower:
                continue

            # Look for model_release events from this org within max_lag_days
            if paper.enriched_at:
                window_start = paper.enriched_at - timedelta(days=max_lag_days)
                window_end = paper.enriched_at + timedelta(days=max_lag_days)
            else:
                continue

            release_stmt = (
                select(EventRecord)
                .where(EventRecord.organization == org)
                .where(EventRecord.event_type == "model_release")
                .where(EventRecord.observed_at >= window_start)
                .where(EventRecord.observed_at <= window_end)
                .order_by(EventRecord.observed_at.asc())
                .limit(1)
            )
            release_result = await session.execute(release_stmt)
            release_event = release_result.scalar_one_or_none()

            if release_event:
                lag = abs((release_event.observed_at - paper.enriched_at).days)
                links.append(
                    PaperProductLink(
                        paper_title=paper.title,
                        paper_arxiv_id=paper.arxiv_id,
                        model_slug=release_event.model_slug or "unknown",
                        organization=org,
                        lag_days=lag,
                    )
                )

    return links


async def _count_topics(
    session: AsyncSession,
    cutoff: datetime,
) -> dict[str, int]:
    """Count topic frequencies from enriched paper relevance_tags."""
    stmt = (
        select(EnrichedPaper.relevance_tags)
        .where(EnrichedPaper.relevance_tags.is_not(None))
        .where(EnrichedPaper.enriched_at >= cutoff)
    )
    result = await session.execute(stmt)
    rows = result.all()

    counts: dict[str, int] = defaultdict(int)
    for (tags_str,) in rows:
        if tags_str:
            for tag in tags_str.split(","):
                tag = tag.strip().lower()
                if tag:
                    counts[tag] += 1

    return dict(counts)
