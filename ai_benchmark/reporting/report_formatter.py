"""Markdown and JSON formatters for the daily intelligence report."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .report_queries import Article, DailyReport, WeeklyStats

_TYPE_LABELS = {
    "model_release": "Model Release",
    "pricing_change": "Pricing Change",
    "benchmark_result": "Benchmark Result",
    "api_update": "API Update",
    "deprecation": "Deprecation",
    "system_card": "System Card",
    "announcement": "Announcement",
}


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _tier_label(tier: str) -> str:
    return tier.replace("_", " ")


def _format_article(article: Article) -> str:
    """Format a single article as a markdown block."""
    lines: list[str] = []

    # Title (linked if URL available)
    if article.url and article.url.startswith("http"):
        lines.append(f"### [{article.title}]({article.url})")
    else:
        lines.append(f"### {article.title}")

    # Metadata line
    meta = [f"**Publisher:** {article.publisher}"]
    if article.published_date:
        meta.append(f"**Date:** {article.published_date}")
    type_label = _TYPE_LABELS.get(article.event_type, article.event_type)
    meta.append(f"**Type:** {type_label}")
    if article.model_slug:
        meta.append(f"**Model:** `{article.model_slug}`")
    lines.append(" | ".join(meta))

    # Source confidence
    status_parts = [f"{_tier_label(article.confidence_tier)}"]
    if article.source_count > 1:
        status_parts.append(f"{article.source_count} sources")
    if article.confirmation_status != "unconfirmed":
        status_parts.append(article.confirmation_status)
    lines.append(f"*{', '.join(status_parts)}*")
    lines.append("")

    # Abstract — the actual content
    if article.abstract:
        lines.append(article.abstract)
        lines.append("")

    # Cross-references
    if article.cross_refs:
        for x in article.cross_refs:
            lines.append(f"> **{x.relationship_type}:** {x.other_title[:100]} ({x.other_org})")
        lines.append("")

    return "\n".join(lines)


def _format_article_list(articles: list[Article]) -> str:
    """Format a list of articles, grouped by publisher."""
    if not articles:
        return "No articles in this period.\n"

    # Group by publisher
    by_publisher: dict[str, list[Article]] = {}
    for a in articles:
        by_publisher.setdefault(a.publisher, []).append(a)

    lines: list[str] = []
    for publisher in sorted(by_publisher, key=lambda p: len(by_publisher[p]), reverse=True):
        pub_articles = by_publisher[publisher]
        lines.append(f"## {publisher} ({len(pub_articles)})")
        lines.append("")
        for a in pub_articles:
            lines.append(_format_article(a))

    return "\n".join(lines)


def _format_weekly_stats(stats: WeeklyStats) -> str:
    """Format the weekly summary statistics."""
    lines: list[str] = []

    lines.append(
        f"**{stats.total_events}** events, "
        f"**{stats.total_unique_claims}** unique claims, "
        f"**{stats.confirmed_count}** confirmed, "
        f"**{stats.conflicted_count}** conflicted"
    )
    lines.append("")

    # Activity by org
    lines.append("| Organization | Events | Top Type |")
    lines.append("|---|---|---|")
    for org in stats.by_org[:15]:
        if org.by_type:
            top_type = max(org.by_type, key=org.by_type.get)
            top_count = org.by_type[top_type]
            lines.append(f"| {org.organization} | {org.event_count} | {top_type} ({top_count}) |")
        else:
            lines.append(f"| {org.organization} | {org.event_count} | - |")
    lines.append("")

    # Model activity
    if stats.model_activity:
        lines.append("| Model | Mentions |")
        lines.append("|---|---|")
        for slug, cnt in stats.model_activity.items():
            lines.append(f"| `{slug}` | {cnt} |")
        lines.append("")

    return "\n".join(lines)


# ─── Public API ───


def format_markdown(data: DailyReport) -> str:
    """Render the full daily report as markdown."""
    lines: list[str] = [
        "# AI Benchmark Daily Report",
        f"Generated: {_fmt_dt(data.generated_at)}",
        "",
        "---",
        "",
        f"# Last 24 Hours ({len(data.yesterday)} articles)",
        "",
        _format_article_list(data.yesterday),
        "---",
        "",
        "# 7-Day Summary",
        "",
        _format_weekly_stats(data.weekly_stats),
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
