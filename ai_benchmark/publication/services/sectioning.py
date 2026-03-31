"""Section assignment: map scored candidates to editorial sections."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import PublicationSettings
    from ..types import ScoredCandidate

# Canonical section definitions in display order.
SECTION_DEFS: list[tuple[str, str]] = [
    ("top_summary", "Top Summary"),
    ("benchmark_movers", "Benchmark Movers"),
    ("announcements", "Model & Vendor Announcements"),
    ("research_pulse", "Research Pulse"),
    ("industry_news", "Industry News"),
    ("watchlist", "Watchlist"),
]

# Map event_type → primary section key.
_TYPE_TO_SECTION: dict[str, str] = {
    "benchmark_result": "benchmark_movers",
    "benchmark_update": "benchmark_movers",
    "model_release": "announcements",
    "model_update": "announcements",
    "deprecation": "announcements",
    "pricing_change": "announcements",
    "system_card": "announcements",
    "release_notes": "announcements",
    "product_announcement": "announcements",
    "company_announcement": "announcements",
    "research": "research_pulse",
    "paper": "research_pulse",
    "news": "industry_news",
    "partnership": "industry_news",
    "policy": "industry_news",
    "infrastructure": "industry_news",
    "funding": "industry_news",
}


async def assign_sections(
    scored: list[ScoredCandidate],
    settings: PublicationSettings,
) -> dict[str, list[ScoredCandidate]]:
    """Assign scored candidates to editorial sections.

    - Maps event_type to section_key via ``_TYPE_TO_SECTION``.
    - Unknown types go to ``industry_news``.
    - Items below ``settings.min_score_threshold`` go to ``watchlist``.
    - Items beyond ``settings.max_items_per_section`` overflow to ``watchlist``.
    - Ties are resolved by score descending, then observed_at ascending (already sorted).
    - Top-scoring items (up to 3) are also referenced in ``top_summary``.
    """
    max_per_section = settings.max_items_per_section
    min_score = settings.min_score_threshold

    max_org_pct = settings.max_org_pct_per_section
    min_per_section = settings.min_items_per_section

    sections: dict[str, list[ScoredCandidate]] = {key: [] for key, _ in SECTION_DEFS}

    for sc in scored:
        # Determine target section
        target = _TYPE_TO_SECTION.get(sc.candidate.event_type, "industry_news")

        # Below threshold → watchlist
        if sc.score < min_score:
            sc.section_key = "watchlist"
            sections["watchlist"].append(sc)
            continue

        # Over capacity → watchlist
        if len(sections[target]) >= max_per_section:
            sc.section_key = "watchlist"
            sections["watchlist"].append(sc)
            continue

        # Org diversity: don't let one org dominate a section
        if max_org_pct < 1.0 and sc.candidate.organization and sections[target]:
            org_count = sum(
                1 for s in sections[target] if s.candidate.organization == sc.candidate.organization
            )
            if org_count / (len(sections[target]) + 1) > max_org_pct:
                sc.section_key = "watchlist"
                sections["watchlist"].append(sc)
                continue

        sc.section_key = target
        sections[target].append(sc)

    # Promote from watchlist if primary sections are thin
    if min_per_section > 0:
        for key, _ in SECTION_DEFS:
            if key in ("top_summary", "watchlist"):
                continue
            while len(sections[key]) < min_per_section and sections["watchlist"]:
                promoted = sections["watchlist"].pop(0)
                promoted.section_key = key
                sections[key].append(promoted)

    # Build top_summary from highest-scoring items across all sections (excluding watchlist)
    all_placed = []
    for key, items in sections.items():
        if key not in ("top_summary", "watchlist"):
            all_placed.extend(items)
    all_placed.sort(key=lambda s: (-s.score, s.candidate.observed_at))
    sections["top_summary"] = all_placed[:3]

    return sections
