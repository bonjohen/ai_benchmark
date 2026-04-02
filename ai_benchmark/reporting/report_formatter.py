"""Markdown and JSON formatters for the daily intelligence report."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .report_queries import DailyReport, EventDetail, RecentChangesReport, WeeklySummaryReport

# High-signal event types that get their own section
_HIGHLIGHT_TYPES = ("model_release", "pricing_change", "benchmark_result")

_TYPE_LABELS = {
    "model_release": "Model Releases",
    "pricing_change": "Pricing Changes",
    "benchmark_result": "Benchmark Results",
    "api_update": "API Updates",
    "deprecation": "Deprecations",
    "system_card": "System Cards",
    "announcement": "Announcements",
}


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _tier_short(tier: str) -> str:
    return tier.replace("_", " ")


def _format_event_block(event: EventDetail) -> str:
    """Format a single event as a markdown block."""
    lines: list[str] = []
    slug_part = f"Model: `{event.model_slug}`" if event.model_slug else ""
    date_part = f"Published: {event.published_date}" if event.published_date else ""
    meta_parts = [p for p in [slug_part, date_part, f"Observed: {_fmt_dt(event.observed_at)}"] if p]
    lines.append(f"- **{event.title}** -- {event.organization}")
    lines.append(f"  {' | '.join(meta_parts)}")

    if event.claims:
        for c in event.claims[:5]:  # Cap displayed claims
            status_badge = c.confirmation_status
            lines.append(
                f"  - {c.claim_text[:120]}"
                f" [{_tier_short(c.confidence_tier)}, {status_badge}]"
                f" -- {c.source_name}"
            )
        if len(event.claims) > 5:
            lines.append(f"  - ... and {len(event.claims) - 5} more claims")

    xrefs = [x for x in event.cross_refs if x.relationship_type in ("confirms", "conflicts_with")]
    for x in xrefs[:3]:
        lines.append(
            f'  - {x.relationship_type}: "{x.other_event_title[:80]}" ({x.other_event_org})'
        )

    return "\n".join(lines)


def _format_recent_changes(data: RecentChangesReport) -> str:
    """Format Part 1: Recent Changes."""
    lines: list[str] = []
    lines.append(f"## Recent Changes (Last {data.window_hours} Hours)")
    lines.append("")

    if data.total_count == 0:
        lines.append("No new events detected in this window.")
        return "\n".join(lines)

    lines.append(f"**{data.total_count}** events observed.")
    lines.append("")

    # Group by event type
    grouped: dict[str, list[EventDetail]] = {}
    for e in data.events:
        grouped.setdefault(e.event_type, []).append(e)

    # Render highlight sections first
    for etype in _HIGHLIGHT_TYPES:
        events = grouped.pop(etype, [])
        if not events:
            continue
        label = _TYPE_LABELS.get(etype, etype)
        lines.append(f"### {label}")
        lines.append("")
        for e in events:
            lines.append(_format_event_block(e))
            lines.append("")

    # Remaining types grouped as "Other"
    remaining = [e for events in grouped.values() for e in events]
    if remaining:
        lines.append("### Other Events")
        lines.append("")
        for e in remaining:
            lines.append(_format_event_block(e))
            lines.append("")

    return "\n".join(lines)


def _format_weekly_summary(data: WeeklySummaryReport) -> str:
    """Format Part 2: 7-Day Summary."""
    lines: list[str] = []
    lines.append(f"## {data.window_days}-Day Summary")
    lines.append("")

    if data.total_events == 0:
        lines.append("No events recorded in this window.")
        return "\n".join(lines)

    org_count = len(data.by_org)
    lines.append(
        f"**{data.total_events}** events and **{data.total_claims}** claims"
        f" from **{org_count}** organizations."
    )
    lines.append("")

    # Activity by Organization
    lines.append("### Activity by Organization")
    lines.append("")
    lines.append("| Organization | Events | Top Type |")
    lines.append("|---|---|---|")
    for org in data.by_org[:15]:
        top_type = max(org.by_type, key=org.by_type.get) if org.by_type else "-"
        top_count = org.by_type.get(top_type, 0) if org.by_type else 0
        lines.append(f"| {org.organization} | {org.event_count} | {top_type} ({top_count}) |")
    if len(data.by_org) > 15:
        lines.append(f"| ... | {len(data.by_org) - 15} more orgs | |")
    lines.append("")

    # Activity by Type
    lines.append("### Activity by Type")
    lines.append("")
    lines.append("| Type | Count |")
    lines.append("|---|---|")
    for etype, cnt in sorted(data.by_type.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {etype} | {cnt} |")
    lines.append("")

    # Confirmed Events
    if data.confirmed_events:
        lines.append(f"### Confirmed Events ({len(data.confirmed_events)})")
        lines.append("")
        for e in data.confirmed_events[:10]:
            confirm_count = sum(1 for c in e.claims if c.confirmation_status == "confirmed")
            lines.append(
                f"- **{e.title}** ({e.organization}) -- {confirm_count} confirming claim(s)"
            )
        if len(data.confirmed_events) > 10:
            lines.append(f"- ... and {len(data.confirmed_events) - 10} more")
        lines.append("")

    # Conflicts
    if data.conflicted_events:
        lines.append(f"### Conflicts Detected ({len(data.conflicted_events)})")
        lines.append("")
        for e in data.conflicted_events[:10]:
            conflict_count = sum(1 for c in e.claims if c.confirmation_status == "conflicted")
            lines.append(
                f"- **{e.title}** ({e.organization}) -- {conflict_count} conflicting claim(s)"
            )
        if len(data.conflicted_events) > 10:
            lines.append(f"- ... and {len(data.conflicted_events) - 10} more")
        lines.append("")

    # Model Activity
    if data.model_activity:
        lines.append("### Model Activity")
        lines.append("")
        lines.append("| Model | Claims |")
        lines.append("|---|---|")
        for slug, cnt in data.model_activity.items():
            lines.append(f"| {slug} | {cnt} |")
        lines.append("")

    # Notable Cross-References
    if data.notable_cross_refs:
        lines.append(f"### Notable Cross-References ({len(data.notable_cross_refs)})")
        lines.append("")
        for x in data.notable_cross_refs:
            lines.append(f"- **{x.relationship_type}**: {x.other_event_title}")
        lines.append("")

    return "\n".join(lines)


# ─── Public API ───


def format_markdown(data: DailyReport) -> str:
    """Render the full daily report as markdown."""
    lines: list[str] = [
        "# AI Benchmark Daily Report",
        f"Generated: {_fmt_dt(data.recent_changes.generated_at)}",
        "",
        "---",
        "",
        _format_recent_changes(data.recent_changes),
        "---",
        "",
        _format_weekly_summary(data.weekly_summary),
    ]
    return "\n".join(lines)


def _default_serializer(obj: object) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    msg = f"Object of type {type(obj)} is not JSON serializable"
    raise TypeError(msg)


def format_json(data: DailyReport) -> str:
    """Render the full daily report as JSON."""
    return json.dumps(asdict(data), indent=2, default=_default_serializer)
