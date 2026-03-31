"""Text rendering: generate human-readable text for edition, sections, and entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..services.sectioning import SECTION_DEFS

if TYPE_CHECKING:
    from ..types import ScoredCandidate


def render_edition_summary(sections: dict[str, list[ScoredCandidate]]) -> str:
    """Generate a short edition summary from the top items."""
    top = sections.get("top_summary", [])
    if not top:
        return "No significant AI developments to report today."

    headlines = [_entry_headline(sc) for sc in top[:3]]
    if len(headlines) == 1:
        return f"Today's top story: {headlines[0]}."
    lead = "; ".join(headlines[:-1])
    return f"Today's top stories: {lead}; and {headlines[-1]}."


def render_section_summary(section_key: str, items: list[ScoredCandidate]) -> str:
    """Generate a short section summary."""
    if not items:
        return ""
    title = _section_title(section_key)
    count = len(items)
    if count == 1:
        return f"One notable {title.lower()} development today."
    return f"{count} notable {title.lower()} developments today."


def render_entry_text(sc: ScoredCandidate) -> dict[str, str]:
    """Generate headline, summary, and why_it_matters for a single entry.

    Returns dict with keys: title, summary, why_it_matters.
    All text is deterministic template-based generation (no LLM calls).
    """
    c = sc.candidate
    title = c.title

    # Build summary from available data
    parts: list[str] = []
    if c.organization:
        parts.append(c.organization)
    if c.model_slug:
        parts.append(f"model {c.model_slug}")
    if c.benchmark_name:
        parts.append(f"on {c.benchmark_name}")

    summary = f"{title} — {', '.join(parts)}." if parts else title

    # Verification context
    verification_note = ""
    if c.verification_status == "confirmed":
        verification_note = f"Confirmed by {c.source_count} source(s)"
        if c.confidence_tier:
            verification_note += f" at {c.confidence_tier.replace('_', ' ')} level"
        verification_note += "."
    elif c.verification_status == "conflicted":
        verification_note = "Conflicting reports from multiple sources."
    elif c.verification_status == "unconfirmed":
        verification_note = "Not yet independently confirmed."

    # Why it matters
    why_parts: list[str] = []
    if c.event_type == "model_release":
        why_parts.append("New model release signals capability expansion")
    elif c.event_type in ("benchmark_result", "benchmark_update"):
        why_parts.append("Benchmark movement indicates shifting competitive position")
    elif c.event_type == "pricing_change":
        why_parts.append("Pricing change affects model accessibility and market dynamics")
    elif c.event_type == "research":
        why_parts.append("Research development may influence future model capabilities")
    else:
        why_parts.append("Notable development in the AI industry")

    if c.cross_ref_count > 0:
        why_parts.append(f"corroborated by {c.cross_ref_count} cross-reference(s)")
    if verification_note:
        why_parts.append(verification_note)

    why_it_matters = ". ".join(why_parts) + "." if why_parts else ""
    # Clean double periods
    why_it_matters = why_it_matters.replace("..", ".")

    return {
        "title": title,
        "summary": summary,
        "why_it_matters": why_it_matters,
    }


def _entry_headline(sc: ScoredCandidate) -> str:
    """Build a short headline string for the top summary."""
    c = sc.candidate
    if c.organization and c.model_slug:
        return f"{c.organization}'s {c.model_slug} ({c.event_type.replace('_', ' ')})"
    if c.organization:
        return f"{c.organization}: {c.title}"
    return c.title


def _section_title(section_key: str) -> str:
    """Look up display title for a section key."""
    for key, title in SECTION_DEFS:
        if key == section_key:
            return title
    return section_key.replace("_", " ").title()
