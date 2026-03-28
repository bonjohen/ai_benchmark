"""Verification hierarchy engine — confirms claims across source tiers.

Five verification chains:
1. Model releases: vendor launch surface > docs/catalog > pricing > changelog > system card.
   Confirmed when 2+ official surfaces agree.
2. Benchmark claims: benchmark owner first, not vendor. Record variant + conditions.
3. Pricing changes: confirmed only when official pricing page changes.
4. Announcements: newsroom > docs > Reuters > other outlets.
5. Research claims: primary paper > Semantic Scholar metadata > company blog.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.events import ClaimRecord, EventRecord


# Source type ordering for each verification chain
VERIFICATION_CHAINS: dict[str, list[str]] = {
    "model_release": [
        "launch_page", "developer_docs", "model_catalog",
        "pricing_page", "changelog", "release_notes", "system_card",
    ],
    "benchmark_result": [
        "benchmark_owner_leaderboard", "benchmark_owner_report",
        "vendor_blog", "vendor_newsroom", "news_outlet",
    ],
    "pricing_change": [
        "pricing_page",
    ],
    "announcement": [
        "newsroom", "developer_docs", "product_page",
        "reuters", "news_outlet", "community",
    ],
    "research_claim": [
        "primary_paper", "arxiv", "semantic_scholar",
        "vendor_blog", "news_outlet",
    ],
}

# Confidence tier by source classification
CLAIM_LABELS: dict[str, str] = {
    "primary": "official_self_report",
    "secondary": "independent_report",
    "discovery-only": "community_signal",
    # Specific overrides
    "benchmark_owner": "benchmark_owner_report",
    "news_high": "reputable_news_report",
    "news_medium": "news_discovery",
    "research_primary": "primary_paper",
}


async def create_claim(
    session: AsyncSession,
    event: EventRecord | None,
    claim_text: str,
    source_type: str,
    source_name: str,
    confidence_tier: str,
    page_title: str | None = None,
) -> ClaimRecord:
    """Create a separate ClaimRecord. Never merge conflicting claims."""
    claim = ClaimRecord(
        event_id=event.id if event else None,
        claim_text=claim_text,
        source_type=source_type,
        source_name=source_name,
        page_title=page_title,
        confidence_tier=confidence_tier,
        confirmation_status="unconfirmed",
        observed_at=datetime.now(timezone.utc),
    )
    session.add(claim)
    await session.flush()
    return claim


async def check_confirmation(
    session: AsyncSession,
    event: EventRecord,
    min_sources: int = 2,
) -> bool:
    """Check if an event has enough confirming claims to be marked confirmed.

    For model releases: requires 2+ official surfaces.
    For benchmark claims: requires benchmark owner claim.
    For pricing: requires pricing_page source.
    """
    stmt = select(ClaimRecord).where(ClaimRecord.event_id == event.id)
    result = await session.execute(stmt)
    claims = list(result.scalars().all())

    if not claims:
        return False

    event_type = event.event_type
    chain = VERIFICATION_CHAINS.get(event_type, [])

    if event_type == "model_release":
        official_claims = [c for c in claims if c.confidence_tier == "official_self_report"]
        return len(official_claims) >= min_sources

    if event_type == "benchmark_result":
        return any(c.confidence_tier == "benchmark_owner_report" for c in claims)

    if event_type == "pricing_change":
        return any(c.source_type == "pricing_page" for c in claims)

    if event_type == "announcement":
        # Confirmed if newsroom + one other source
        has_newsroom = any("newsroom" in c.source_type for c in claims)
        return has_newsroom and len(claims) >= min_sources

    if event_type in ("research_claim", "research"):
        return any(c.confidence_tier == "primary_paper" for c in claims)

    # Default: 2+ claims from any tier
    return len(claims) >= min_sources


async def update_confirmation_status(
    session: AsyncSession,
    event: EventRecord,
) -> str:
    """Update the confirmation status of all claims for an event.

    Returns the new status: 'confirmed', 'conflicted', or 'unconfirmed'.
    """
    stmt = select(ClaimRecord).where(ClaimRecord.event_id == event.id)
    result = await session.execute(stmt)
    claims = list(result.scalars().all())

    if not claims:
        return "unconfirmed"

    # Check for conflicts (claims with different confidence tiers disagreeing)
    claim_texts_lower = [c.claim_text.lower() for c in claims]
    has_conflict = False
    for i, text_a in enumerate(claim_texts_lower):
        for text_b in claim_texts_lower[i + 1:]:
            # Simple conflict detection: if claim texts are very different
            # for the same event, flag as conflicted
            from difflib import SequenceMatcher
            if SequenceMatcher(None, text_a, text_b).ratio() < 0.5:
                has_conflict = True
                break
        if has_conflict:
            break

    if has_conflict:
        new_status = "conflicted"
    elif await check_confirmation(session, event):
        new_status = "confirmed"
    else:
        new_status = "unconfirmed"

    for claim in claims:
        claim.confirmation_status = new_status
    await session.flush()
    return new_status
