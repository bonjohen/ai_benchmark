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

import re
from datetime import datetime, timezone, UTC

from sqlalchemy import select

from ..models.events import ClaimRecord, EventRecord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Source type ordering for each verification chain
VERIFICATION_CHAINS: dict[str, list[str]] = {
    "model_release": [
        "launch_page",
        "developer_docs",
        "model_catalog",
        "pricing_page",
        "changelog",
        "release_notes",
        "system_card",
    ],
    "benchmark_result": [
        "benchmark_owner_leaderboard",
        "benchmark_owner_report",
        "vendor_blog",
        "vendor_newsroom",
        "news_outlet",
    ],
    "pricing_change": [
        "pricing_page",
    ],
    "announcement": [
        "newsroom",
        "developer_docs",
        "product_page",
        "reuters",
        "news_outlet",
        "community",
    ],
    "research_claim": [
        "primary_paper",
        "arxiv",
        "semantic_scholar",
        "vendor_blog",
        "news_outlet",
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
        observed_at=datetime.now(UTC),
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

    Enforces the verification chain ordering defined in VERIFICATION_CHAINS:
    - Model releases: 2+ distinct source types from the chain, with at least
      one from the top 3 ranked source types.
    - Benchmark claims: requires a claim with benchmark_owner_report tier.
    - Pricing: requires a pricing_page source claim.
    - Announcements: newsroom + 1 other.
    - Research: requires a primary_paper claim.
    """
    stmt = select(ClaimRecord).where(ClaimRecord.event_id == event.id)
    result = await session.execute(stmt)
    claims = list(result.scalars().all())

    if not claims:
        return False

    event_type = event.event_type
    chain = VERIFICATION_CHAINS.get(event_type, [])

    if event_type == "model_release":
        # Require 2+ distinct source types that appear in the chain,
        # with at least one from the top 3 of the chain
        top_types = set(chain[:3]) if len(chain) >= 3 else set(chain)
        chain_set = set(chain)
        matching_types = {c.source_type for c in claims if c.source_type in chain_set}
        has_high_rank = bool(matching_types & top_types)
        return len(matching_types) >= min_sources and has_high_rank

    if event_type == "benchmark_result":
        return any(c.confidence_tier == "benchmark_owner_report" for c in claims)

    if event_type == "pricing_change":
        return any(c.source_type == "pricing_page" for c in claims)

    if event_type == "announcement":
        has_newsroom = any("newsroom" in c.source_type for c in claims)
        return has_newsroom and len(claims) >= min_sources

    if event_type in ("research_claim", "research"):
        return any(c.confidence_tier == "primary_paper" for c in claims)

    # Default: 2+ claims from any tier
    return len(claims) >= min_sources


def _extract_numbers(text: str) -> list[float]:
    """Extract numeric values from claim text for conflict comparison.

    Prioritizes percentage values to avoid picking up model version numbers.
    """
    pcts = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if pcts:
        return pcts
    return [float(m) for m in re.findall(r"(?<![-\w])(\d{2,}(?:\.\d+)?)", text)]


def detect_claim_conflict(claim_a: ClaimRecord, claim_b: ClaimRecord) -> bool:
    """Detect if two claims conflict based on numerical value disagreement.

    Returns True when both claims contain numbers and the first extracted
    values differ by more than 10%.
    """
    nums_a = _extract_numbers(claim_a.claim_text)
    nums_b = _extract_numbers(claim_b.claim_text)
    if nums_a and nums_b:
        val_a, val_b = nums_a[0], nums_b[0]
        if val_a > 0 and abs(val_a - val_b) / val_a > 0.10:
            return True
    return False


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

    # Check for conflicts using numerical value disagreement
    has_conflict = False
    for i, claim_a in enumerate(claims):
        for claim_b in claims[i + 1 :]:
            if detect_claim_conflict(claim_a, claim_b):
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
