"""Markdown rendering for analysis results."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AnalysisInsight
    from ..types import (
        ActivityTimeline,
        Leaderboard,
        ModelProfile,
        ModelSummary,
        ResearchTrends,
    )


def model_list_to_markdown(models: list[ModelSummary]) -> str:
    """Render a model listing as Markdown."""
    if not models:
        return "No tracked models found.\n"

    lines = ["# Tracked Models", ""]
    lines.append("| Model | Organization | First Seen | Latest | Events | Status |")
    lines.append("|---|---|---|---|---|---|")
    for m in models:
        lines.append(
            f"| {m.model_slug} | {m.organization} "
            f"| {m.first_seen or '—'} | {m.latest_activity or '—'} "
            f"| {m.event_count} | {m.status} |"
        )
    lines.append("")
    return "\n".join(lines)


def model_profile_to_markdown(profile: ModelProfile) -> str:
    """Render a model profile as Markdown."""
    lines = [
        f"# {profile.model_slug}",
        "",
        f"**Organization:** {profile.organization}",
        f"**Status:** {profile.status}",
        f"**First seen:** {profile.first_seen or '—'}",
        f"**Latest activity:** {profile.latest_activity or '—'}",
        "",
    ]

    # Claims
    if profile.claim_summary:
        lines.append("## Claims")
        lines.append("")
        for status, count in sorted(profile.claim_summary.items()):
            lines.append(f"- **{status}:** {count}")
        lines.append("")

    # Timeline
    if profile.milestones:
        lines.append("## Timeline")
        lines.append("")
        lines.append("| Date | Type | Title | Confidence | Status |")
        lines.append("|---|---|---|---|---|")
        for m in profile.milestones:
            lines.append(
                f"| {m.date} | {m.event_type} | {m.title} "
                f"| {m.confidence_tier} | {m.confirmation_status} |"
            )
        lines.append("")

    # Benchmark scores
    if profile.benchmark_scores:
        lines.append("## Benchmark Scores")
        lines.append("")
        lines.append("| Benchmark | Score | Date | Source |")
        lines.append("|---|---|---|---|")
        for b in profile.benchmark_scores:
            score_str = f"{b.score}" if b.score is not None else "—"
            lines.append(f"| {b.benchmark_variant} | {score_str} | {b.date} | {b.source_name} |")
        lines.append("")

    # Related models
    if profile.related_models:
        lines.append("## Related Models")
        lines.append("")
        for slug in profile.related_models:
            lines.append(f"- {slug}")
        lines.append("")

    return "\n".join(lines)


def leaderboard_to_markdown(leaderboard: Leaderboard) -> str:
    """Render a benchmark leaderboard as Markdown."""
    lines = [
        f"# {leaderboard.benchmark_name}",
        "",
        f"**As of:** {leaderboard.as_of}",
        "",
    ]
    if not leaderboard.entries:
        lines.append("No entries found.\n")
        return "\n".join(lines)

    lines.append("| Rank | Model | Score | Date | Source |")
    lines.append("|---|---|---|---|---|")
    for i, entry in enumerate(leaderboard.entries, 1):
        score_str = f"{entry.score}" if entry.score is not None else "—"
        lines.append(
            f"| {i} | {entry.model_slug} | {score_str} | {entry.date} | {entry.source_name} |"
        )
    lines.append("")
    return "\n".join(lines)


def activity_timeline_to_markdown(timeline: ActivityTimeline) -> str:
    """Render a competitive activity timeline as Markdown."""
    lines = [
        "# Competitive Activity",
        "",
        f"**Window:** {timeline.window_start} to {timeline.window_end}",
        "",
    ]

    if timeline.org_activities:
        lines.append("## Organization Activity")
        lines.append("")
        lines.append("| Organization | Events | Active Models |")
        lines.append("|---|---|---|")
        for org in timeline.org_activities:
            models_str = ", ".join(org.active_models[:5])
            if len(org.active_models) > 5:
                models_str += f" (+{len(org.active_models) - 5} more)"
            lines.append(f"| {org.organization} | {org.total_events} | {models_str} |")
        lines.append("")

    if timeline.clusters:
        lines.append("## Competitive Clusters")
        lines.append("")
        for cluster in timeline.clusters:
            orgs = ", ".join(cluster.organizations)
            lines.append(
                f"- **{cluster.event_type}** ({cluster.start_date} to {cluster.end_date}): "
                f"{orgs} ({cluster.event_count} events)"
            )
        lines.append("")

    return "\n".join(lines)


def research_trends_to_markdown(trends: ResearchTrends) -> str:
    """Render research trends as Markdown."""
    lines = [
        "# Research Pulse",
        "",
        f"**Window:** {trends.window_days} days",
        f"**Papers:** {trends.total_papers} total "
        f"({trends.promoted_count} promoted, "
        f"{trends.rejected_count} rejected, "
        f"{trends.pending_count} pending)",
        "",
    ]

    if trends.citation_leaders:
        lines.append("## Citation Leaders")
        lines.append("")
        lines.append("| Title | Citations | Venue | arXiv |")
        lines.append("|---|---|---|---|")
        for p in trends.citation_leaders:
            lines.append(
                f"| {p.title} | {p.citation_count} | {p.venue or '—'} | {p.arxiv_id or '—'} |"
            )
        lines.append("")

    if trends.topic_counts:
        lines.append("## Trending Topics")
        lines.append("")
        sorted_topics = sorted(trends.topic_counts.items(), key=lambda x: -x[1])
        for topic, count in sorted_topics[:15]:
            lines.append(f"- **{topic}:** {count}")
        lines.append("")

    if trends.paper_product_links:
        lines.append("## Paper-to-Product Links")
        lines.append("")
        for link in trends.paper_product_links:
            lines.append(
                f"- {link.paper_title} -> {link.model_slug} "
                f"({link.organization}, {link.lag_days}d lag)"
            )
        lines.append("")

    return "\n".join(lines)


def insights_to_markdown(insights: list[AnalysisInsight]) -> str:
    """Render analysis insights as Markdown."""
    if not insights:
        return "No insights detected.\n"

    lines = ["# Analysis Insights", ""]
    severity_order = {"critical": 0, "notable": 1, "info": 2}
    sorted_insights = sorted(insights, key=lambda i: severity_order.get(i.severity, 3))

    for insight in sorted_insights:
        severity_badge = {"critical": "!!!", "notable": "!!", "info": "i"}.get(insight.severity, "")
        lines.append(f"### [{severity_badge}] {insight.title}")
        lines.append("")
        lines.append(insight.description)
        details = []
        if insight.related_model_slug:
            details.append(f"Model: {insight.related_model_slug}")
        if insight.related_org:
            details.append(f"Org: {insight.related_org}")
        if details:
            lines.append(f"*{', '.join(details)}*")
        lines.append("")

    return "\n".join(lines)
