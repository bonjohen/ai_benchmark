"""Research-to-product pipeline intelligence with citation velocity and topic trends."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from ...models.research import EnrichedPaper
from ..types import CitationVelocityEntry, ResearchPipelineReport, TopicTrend

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_research_pipeline(
    session: AsyncSession,
    *,
    window_days: int = 90,
    min_citations: int = 0,
) -> ResearchPipelineReport:
    """Citation velocity, topic trends, and predictive signals."""
    from .research_pulse import detect_paper_to_product, get_citation_leaders

    # 1. Citation leaders (raw data)
    leaders = await get_citation_leaders(session, limit=100)

    # 2. Compute velocity per paper
    now = datetime.now(UTC)
    velocity_entries: list[CitationVelocityEntry] = []
    for paper in leaders:
        if paper.citation_count < min_citations:
            continue
        # Parse enriched_at date
        if paper.enriched_at:
            try:
                enriched_dt = datetime.strptime(paper.enriched_at, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                enriched_dt = now
        else:
            enriched_dt = now
        weeks = max(1.0, (now - enriched_dt).days / 7.0)
        velocity = paper.citation_count / weeks
        velocity_entries.append(
            CitationVelocityEntry(
                title=paper.title,
                arxiv_id=paper.arxiv_id,
                citation_count=paper.citation_count,
                velocity_per_week=round(velocity, 2),
                venue=paper.venue,
            )
        )

    # Sort by velocity descending
    velocity_entries.sort(key=lambda e: -e.velocity_per_week)

    # 3. Split-window topic trends
    cutoff = now - timedelta(days=window_days)
    midpoint = now - timedelta(days=window_days // 2)
    topic_trends = await _compute_topic_trends(session, cutoff, midpoint)

    # 4. Paper-to-product links
    paper_product_links = await detect_paper_to_product(session, max_lag_days=window_days)

    # 5. Predictive signals: high-velocity papers with tags overlapping productive topics
    productive_tags = _get_productive_tags(paper_product_links, session)
    predictive_signals = await _find_predictive_signals(session, velocity_entries, productive_tags)

    return ResearchPipelineReport(
        window_days=window_days,
        velocity_leaders=velocity_entries[:20],
        topic_trends=topic_trends,
        paper_product_links=paper_product_links,
        predictive_signals=predictive_signals,
    )


async def _compute_topic_trends(
    session: AsyncSession,
    cutoff: datetime,
    midpoint: datetime,
) -> list[TopicTrend]:
    """Compute topic frequency trends using a split window."""
    # Earlier half: cutoff to midpoint
    earlier_stmt = (
        select(EnrichedPaper.relevance_tags)
        .where(EnrichedPaper.relevance_tags.is_not(None))
        .where(EnrichedPaper.enriched_at >= cutoff)
        .where(EnrichedPaper.enriched_at < midpoint)
    )
    earlier_result = await session.execute(earlier_stmt)
    earlier_counts = _count_tags([r[0] for r in earlier_result.all()])

    # Recent half: midpoint to now
    recent_stmt = (
        select(EnrichedPaper.relevance_tags)
        .where(EnrichedPaper.relevance_tags.is_not(None))
        .where(EnrichedPaper.enriched_at >= midpoint)
    )
    recent_result = await session.execute(recent_stmt)
    recent_counts = _count_tags([r[0] for r in recent_result.all()])

    # Merge all topics
    all_topics = set(earlier_counts.keys()) | set(recent_counts.keys())
    trends = []
    for topic in sorted(all_topics):
        earlier = earlier_counts.get(topic, 0)
        recent = recent_counts.get(topic, 0)
        total = earlier + recent
        if recent > earlier:
            direction = "rising"
        elif recent < earlier:
            direction = "falling"
        else:
            direction = "stable"
        trends.append(
            TopicTrend(
                topic=topic,
                total_count=total,
                recent_count=recent,
                earlier_count=earlier,
                direction=direction,
            )
        )

    # Sort by total count descending
    trends.sort(key=lambda t: -t.total_count)
    return trends


def _count_tags(tag_strings: list[str | None]) -> dict[str, int]:
    """Count individual tags from comma-separated tag strings."""
    counts: dict[str, int] = defaultdict(int)
    for tags_str in tag_strings:
        if tags_str:
            for tag in tags_str.split(","):
                tag = tag.strip().lower()
                if tag:
                    counts[tag] += 1
    return dict(counts)


def _get_productive_tags(paper_product_links, session) -> set[str]:
    """Extract tags from papers that have paper-product links."""
    # We just collect the arxiv_ids that appear in links
    return {link.paper_arxiv_id for link in paper_product_links if link.paper_arxiv_id}


async def _find_predictive_signals(
    session: AsyncSession,
    velocity_entries: list[CitationVelocityEntry],
    productive_arxiv_ids: set[str],
) -> list[CitationVelocityEntry]:
    """Find high-velocity papers whose arxiv_ids overlap with productive papers."""
    if not velocity_entries:
        return []

    # Median velocity
    velocities = sorted(e.velocity_per_week for e in velocity_entries)
    mid = len(velocities) // 2
    median_velocity = (
        velocities[mid] if len(velocities) % 2 else (velocities[mid - 1] + velocities[mid]) / 2
    )

    # Also check relevance_tags overlap with productive paper tags
    if productive_arxiv_ids:
        # Get tags for productive papers
        stmt = (
            select(EnrichedPaper.relevance_tags)
            .where(EnrichedPaper.arxiv_id.in_(list(productive_arxiv_ids)))
            .where(EnrichedPaper.relevance_tags.is_not(None))
        )
        result = await session.execute(stmt)
        productive_tags: set[str] = set()
        for (tags_str,) in result.all():
            if tags_str:
                for tag in tags_str.split(","):
                    tag = tag.strip().lower()
                    if tag:
                        productive_tags.add(tag)
    else:
        productive_tags = set()

    signals = []
    for entry in velocity_entries:
        if entry.velocity_per_week <= median_velocity:
            continue

        # Check if this paper has tags overlapping productive topics
        if productive_tags and entry.arxiv_id:
            paper_stmt = select(EnrichedPaper.relevance_tags).where(
                EnrichedPaper.arxiv_id == entry.arxiv_id
            )
            paper_result = await session.execute(paper_stmt)
            row = paper_result.first()
            if row and row[0]:
                paper_tags = {t.strip().lower() for t in row[0].split(",") if t.strip()}
                if paper_tags & productive_tags:
                    signals.append(entry)
        elif not productive_tags:
            # No productive tags to compare against — include all high-velocity papers
            signals.append(entry)

    return signals
