"""Markdown rendering for publication editions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EditionResult


def edition_to_markdown(edition: EditionResult) -> str:
    """Render a complete edition as Markdown."""
    lines: list[str] = []

    lines.append(f"# Daily AI Benchmark — {edition.publication_date}")
    lines.append("")

    if edition.summary:
        lines.append(f"*{edition.summary}*")
        lines.append("")

    for section in edition.sections:
        if not section.entries:
            continue

        lines.append(f"## {section.title}")
        lines.append("")

        if section.summary:
            lines.append(f"_{section.summary}_")
            lines.append("")

        for entry in section.entries:
            # Entry header
            badge = _verification_badge(entry.verification_status)
            lines.append(f"### {entry.rank}. {entry.title} {badge}")
            lines.append("")

            lines.append(entry.summary)
            lines.append("")

            if entry.why_it_matters:
                lines.append(f"> **Why it matters:** {entry.why_it_matters}")
                lines.append("")

            # Metadata line
            meta_parts: list[str] = []
            if entry.organization:
                meta_parts.append(f"**Org:** {entry.organization}")
            if entry.model_slug:
                meta_parts.append(f"**Model:** {entry.model_slug}")
            if entry.benchmark_name:
                meta_parts.append(f"**Benchmark:** {entry.benchmark_name}")
            meta_parts.append(f"**Sources:** {entry.source_count}")
            meta_parts.append(f"**Score:** {entry.score:.2f}")

            lines.append(" | ".join(meta_parts))
            lines.append("")

    # Stats footer
    if edition.stats:
        lines.append("---")
        lines.append("")
        lines.append(
            f"*Generated with {edition.stats.get('total_candidates', 0)} candidates, "
            f"{edition.stats.get('total_entries', 0)} entries across "
            f"{edition.stats.get('sections_with_items', 0)} sections.*"
        )
        lines.append("")

    return "\n".join(lines)


def _verification_badge(status: str) -> str:
    """Return a text badge for verification status."""
    return {
        "confirmed": "[confirmed]",
        "unconfirmed": "[unconfirmed]",
        "conflicted": "[conflicted]",
    }.get(status, "")
