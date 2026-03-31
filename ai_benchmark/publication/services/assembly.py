"""Candidate assembly: load eligible items from DB and produce publication candidates."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...analysis.models import AnalysisInsight
from ...models.events import ClaimRecord, CrossReference, EventRecord
from ...models.research import EnrichedPaper
from ..types import CandidateItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..config import PublicationSettings

# Confidence tiers ordered from highest to lowest authority.
_TIER_RANK = {
    "official_self_report": 5,
    "benchmark_owner_report": 4,
    "high_secondary": 3,
    "medium_discovery": 2,
    "low_discovery": 1,
}

# Event types that require benchmark-owner claim support.
_BENCHMARK_TYPES = {"benchmark_result", "benchmark_update"}

# Event types that require pricing verification path.
_PRICING_TYPES = {"pricing_change"}


async def assemble_candidates(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
    settings: PublicationSettings,
) -> list[CandidateItem]:
    """Load eligible items from DB and produce ranked publication candidates.

    Applies eligibility rules per PDR §9.2:
    - Exclude conflicted events unless ``settings.include_low_confidence`` is True
    - Benchmark entries require a benchmark-owner claim
    - Research entries require promoted status
    - Pricing entries require pricing verification path (official_self_report claim)
    - Duplicate candidate representations are collapsed per event cluster
    """
    candidates: list[CandidateItem] = []

    # --- Event-based candidates ---
    event_candidates = await _load_event_candidates(session, window_start, window_end, settings)
    candidates.extend(event_candidates)

    # --- Research-based candidates ---
    research_candidates = await _load_research_candidates(session, window_start, window_end)
    candidates.extend(research_candidates)

    return candidates


async def _load_event_candidates(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    settings: PublicationSettings,
) -> list[CandidateItem]:
    """Load event-based candidates with eligibility filtering."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.observed_at >= window_start)
        .where(EventRecord.observed_at <= window_end)
        .order_by(EventRecord.observed_at.desc())
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    candidates: list[CandidateItem] = []
    seen_keys: set[str] = set()

    for ev in events:
        # --- Eligibility checks ---

        # Load claims for this event
        claims_stmt = select(ClaimRecord).where(ClaimRecord.event_id == ev.id)
        claims_result = await session.execute(claims_stmt)
        claims = claims_result.scalars().all()

        # Determine highest confidence tier and confirmation status
        best_tier = _best_confidence_tier(claims)
        has_conflicted = any(c.confirmation_status == "conflicted" for c in claims)

        # Skip conflicted unless configured to include
        if has_conflicted and not settings.include_low_confidence:
            continue

        # Benchmark entries require benchmark-owner claim
        if ev.event_type in _BENCHMARK_TYPES:
            has_benchmark_owner = any(c.confidence_tier == "benchmark_owner_report" for c in claims)
            if not has_benchmark_owner:
                continue

        # Pricing entries require official self-report claim
        if ev.event_type in _PRICING_TYPES:
            has_official = any(c.confidence_tier == "official_self_report" for c in claims)
            if not has_official:
                continue

        # Dedup by event cluster key
        dedup_key = _event_dedup_key(ev)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # Count cross-references
        xref_count = await _count_cross_refs(session, ev.id)

        # Determine verification status
        verification = "unconfirmed"
        if has_conflicted:
            verification = "conflicted"
        elif any(c.confirmation_status == "confirmed" for c in claims):
            verification = "confirmed"

        # Check for analysis signals (insights)
        signals = await _load_analysis_signals(session, ev.model_slug)

        candidates.append(
            CandidateItem(
                event_id=ev.id,
                paper_id=None,
                title=ev.title,
                organization=ev.organization,
                model_slug=ev.model_slug,
                benchmark_name=ev.benchmark_variant,
                event_type=ev.event_type,
                verification_status=verification,
                confidence_tier=best_tier,
                source_count=len(claims),
                cross_ref_count=xref_count,
                observed_at=ev.observed_at.isoformat() if ev.observed_at else "",
                raw_content=ev.raw_content,
                analysis_signals=signals,
            )
        )

    return candidates


async def _load_research_candidates(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
) -> list[CandidateItem]:
    """Load promoted research papers as publication candidates."""
    stmt = (
        select(EnrichedPaper)
        .where(EnrichedPaper.enriched_at >= window_start)
        .where(EnrichedPaper.enriched_at <= window_end)
        .order_by(EnrichedPaper.citation_count.desc())
    )
    result = await session.execute(stmt)
    papers = result.scalars().all()

    candidates: list[CandidateItem] = []
    for paper in papers:
        # Parse org from authors if available
        org = None
        if paper.authors:
            # Use first author's implied org (best-effort)
            org = paper.authors.split(",")[0].strip() if paper.authors else None

        candidates.append(
            CandidateItem(
                event_id=None,
                paper_id=paper.id,
                title=paper.title,
                organization=org,
                model_slug=None,
                benchmark_name=None,
                event_type="research",
                verification_status="confirmed",
                confidence_tier="high_secondary",
                source_count=1,
                cross_ref_count=0,
                observed_at=paper.enriched_at.isoformat() if paper.enriched_at else "",
                raw_content=paper.abstract,
                analysis_signals={
                    "citation_count": paper.citation_count or 0,
                    "venue": paper.venue,
                },
            )
        )

    return candidates


def _best_confidence_tier(claims: list) -> str:
    """Return the highest-authority confidence tier from a list of claims."""
    if not claims:
        return "low_discovery"
    best = max(claims, key=lambda c: _TIER_RANK.get(c.confidence_tier, 0))
    return best.confidence_tier


def _event_dedup_key(ev: EventRecord) -> str:
    """Produce a dedup key for an event to collapse duplicate candidates."""
    return f"{ev.normalized_title}|{ev.organization}|{ev.event_type}|{ev.model_slug or ''}"


async def _count_cross_refs(session: AsyncSession, event_id: int) -> int:
    """Count cross-references involving this event."""
    stmt = select(func.count(CrossReference.id)).where(
        (CrossReference.record_a_id == event_id) | (CrossReference.record_b_id == event_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def _load_analysis_signals(session: AsyncSession, model_slug: str | None) -> dict:
    """Load relevant analysis insights for a model slug."""
    if not model_slug:
        return {}
    stmt = (
        select(AnalysisInsight.insight_type, AnalysisInsight.severity)
        .where(AnalysisInsight.related_model_slug == model_slug)
        .distinct()
    )
    result = await session.execute(stmt)
    rows = result.all()
    if not rows:
        return {}
    return {
        "insight_types": [r[0] for r in rows],
        "max_severity": max(
            (r[1] for r in rows),
            key=lambda s: {"critical": 3, "notable": 2, "info": 1}.get(s, 0),
        ),
    }
