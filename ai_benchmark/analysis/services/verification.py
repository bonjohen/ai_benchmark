"""Claim verification dashboard: confirmation depth and confidence tier analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import ClaimRecord, CrossReference, EventRecord
from ..types import BenchmarkVerification, ModelVerification, VerificationReport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

CONFIDENCE_TIER_ORDER = [
    "official_self_report",
    "benchmark_owner_report",
    "high_secondary",
    "medium_discovery",
    "low_discovery",
]


async def get_verification_report(
    session: AsyncSession,
    *,
    organization: str | None = None,
    model_slug: str | None = None,
) -> VerificationReport:
    """Build a verification report across models and benchmarks."""
    # 1. Query events
    event_stmt = select(EventRecord)
    if organization:
        event_stmt = event_stmt.where(EventRecord.organization == organization)
    if model_slug:
        event_stmt = event_stmt.where(EventRecord.model_slug == model_slug)
    event_result = await session.execute(event_stmt)
    events = list(event_result.scalars().all())

    if not events:
        return VerificationReport(
            total_events=0,
            total_claims=0,
            confirmation_rate=0.0,
            conflict_rate=0.0,
        )

    event_ids = [e.id for e in events]
    event_by_id = {e.id: e for e in events}

    # 2. Query all claims for these events
    claim_stmt = select(ClaimRecord).where(ClaimRecord.event_id.in_(event_ids))
    claim_result = await session.execute(claim_stmt)
    claims = list(claim_result.scalars().all())

    total_claims = len(claims)
    confirmed_count = sum(1 for c in claims if c.confirmation_status == "confirmed")
    conflicted_count = sum(1 for c in claims if c.confirmation_status == "conflicted")

    confirmation_rate = (confirmed_count / total_claims * 100.0) if total_claims else 0.0
    conflict_rate = (conflicted_count / total_claims * 100.0) if total_claims else 0.0

    # 3. Tier distribution
    tier_dist: dict[str, int] = defaultdict(int)
    for c in claims:
        if c.confidence_tier:
            tier_dist[c.confidence_tier] += 1

    # 4. Per-model verification
    model_claims: dict[str, list[ClaimRecord]] = defaultdict(list)
    model_org: dict[str, str] = {}
    for c in claims:
        event = event_by_id.get(c.event_id)
        if event and event.model_slug:
            model_claims[event.model_slug].append(c)
            if event.organization:
                model_org[event.model_slug] = event.organization

    model_verifications = []
    for slug, slug_claims in sorted(model_claims.items()):
        total = len(slug_claims)
        confirmed = sum(1 for c in slug_claims if c.confirmation_status == "confirmed")
        conflicted = sum(1 for c in slug_claims if c.confirmation_status == "conflicted")
        sources = len({c.source_name for c in slug_claims if c.source_name})
        tiers = [c.confidence_tier for c in slug_claims if c.confidence_tier]
        highest = _highest_tier(tiers)

        # CrossReference confirms count
        slug_event_ids = [e.id for e in events if e.model_slug == slug]
        xref_count = 0
        if slug_event_ids:
            xref_stmt = (
                select(func.count(CrossReference.id))
                .where(
                    (CrossReference.record_a_id.in_(slug_event_ids))
                    | (CrossReference.record_b_id.in_(slug_event_ids))
                )
                .where(CrossReference.relationship_type == "confirms")
            )
            xref_result = await session.execute(xref_stmt)
            xref_count = xref_result.scalar() or 0

        model_verifications.append(
            ModelVerification(
                model_slug=slug,
                organization=model_org.get(slug, ""),
                total_claims=total,
                confirmed_pct=round(confirmed / total * 100.0, 2) if total else 0.0,
                conflicted_pct=round(conflicted / total * 100.0, 2) if total else 0.0,
                source_count=sources,
                highest_confidence_tier=highest,
                xref_confirms_count=xref_count,
            )
        )

    # 5. Per-benchmark verification
    benchmark_claims: dict[str, list] = defaultdict(list)
    for event in events:
        if event.benchmark_variant:
            event_claims = [c for c in claims if c.event_id == event.id]
            benchmark_claims[event.benchmark_variant].extend(event_claims)

    benchmark_verifications = []
    for bvariant, b_claims in sorted(benchmark_claims.items()):
        sources = len({c.source_name for c in b_claims if c.source_name})
        has_conflicts = any(c.confirmation_status == "conflicted" for c in b_claims)

        # Score variance from raw_content
        from .benchmark_trends import extract_benchmark_score

        scores = []
        for event in events:
            if event.benchmark_variant == bvariant and event.raw_content:
                score = extract_benchmark_score(event.raw_content, bvariant)
                if score is not None:
                    scores.append(score)

        variance = None
        if len(scores) >= 2:
            mean = sum(scores) / len(scores)
            variance = round(sum((s - mean) ** 2 for s in scores) / len(scores), 4)

        benchmark_verifications.append(
            BenchmarkVerification(
                benchmark_variant=bvariant,
                source_count=sources,
                has_conflicts=has_conflicts,
                score_variance=variance,
            )
        )

    return VerificationReport(
        total_events=len(events),
        total_claims=total_claims,
        confirmation_rate=round(confirmation_rate, 2),
        conflict_rate=round(conflict_rate, 2),
        tier_distribution=dict(tier_dist),
        model_verifications=model_verifications,
        benchmark_verifications=benchmark_verifications,
    )


def _highest_tier(tiers: list[str]) -> str:
    """Return the highest confidence tier from a list."""
    if not tiers:
        return ""
    for tier in CONFIDENCE_TIER_ORDER:
        if tier in tiers:
            return tier
    return tiers[0]
