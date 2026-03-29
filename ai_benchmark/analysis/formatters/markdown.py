"""Markdown rendering for analysis results."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AnalysisInsight
    from ..types import (
        ActivityTimeline,
        CapabilityProfile,
        DigestReport,
        EvolutionSummary,
        LandscapeReport,
        Leaderboard,
        ModelProfile,
        ModelSummary,
        ResearchTrends,
        SpotlightReport,
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


def digest_to_markdown(digest: DigestReport) -> str:
    """Render a full periodic digest as Markdown."""
    lines = [
        "# Intelligence Digest",
        "",
        f"**Period:** {digest.period_start} to {digest.period_end}",
        "",
    ]

    if digest.stats:
        lines.append("## Summary")
        lines.append("")
        for key, value in digest.stats.items():
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if digest.headline_insights:
        lines.append("## Headline Insights")
        lines.append("")
        for insight in digest.headline_insights:
            severity_badge = {"critical": "!!!", "notable": "!!", "info": "i"}.get(
                insight.get("severity", ""), ""
            )
            lines.append(f"- [{severity_badge}] **{insight.get('title', '')}**")
            if insight.get("description"):
                lines.append(f"  {insight['description']}")
        lines.append("")

    if digest.model_updates:
        lines.append("## Model Updates")
        lines.append("")
        lines.append("| Model | Organization | Events | Status |")
        lines.append("|---|---|---|---|")
        for m in digest.model_updates:
            lines.append(f"| {m.model_slug} | {m.organization} | {m.event_count} | {m.status} |")
        lines.append("")

    if digest.benchmark_movements:
        lines.append("## Benchmark Movements")
        lines.append("")
        lines.append("| Benchmark | Model | Score | Date |")
        lines.append("|---|---|---|---|")
        for b in digest.benchmark_movements:
            score_str = f"{b.score}" if b.score is not None else "—"
            lines.append(f"| {b.benchmark_variant} | {b.model_slug} | {score_str} | {b.date} |")
        lines.append("")

    if digest.spotlight_models:
        lines.append("## New Model Spotlight")
        lines.append("")
        lines.append("| Model | Org | Debut Strength | Benchmarks |")
        lines.append("|---|---|---|---|")
        for s in digest.spotlight_models:
            lines.append(
                f"| {s.model_slug} | {s.organization} | {s.debut_strength} | {s.benchmark_count} |"
            )
        lines.append("")

    if digest.evolution_highlights:
        lines.append("## Benchmark Evolution")
        lines.append("")
        for evo in digest.evolution_highlights:
            if evo.current_leader:
                rate_str = (
                    f"{evo.improvement_rate_per_month:+.2f}/mo"
                    if evo.improvement_rate_per_month is not None
                    else "—"
                )
                lines.append(
                    f"- **{evo.benchmark_name}**: {evo.current_leader} "
                    f"({evo.current_top_score}) {rate_str}"
                )
        lines.append("")

    if digest.competitive_overview:
        lines.append(activity_timeline_to_markdown(digest.competitive_overview))

    if digest.research_highlights:
        lines.append(research_trends_to_markdown(digest.research_highlights))

    return "\n".join(lines)


def spotlight_to_markdown(report: SpotlightReport) -> str:
    """Render a spotlight report as Markdown."""
    lines = [
        "# New Model Spotlight",
        "",
        f"**Window:** {report.window_days} days (since {report.cutoff_date})",
        f"**New models:** {report.total_new_models}",
        "",
    ]

    if not report.entries:
        lines.append("No new models found in this window.\n")
        return "\n".join(lines)

    lines.append("| Model | Org | First Seen | Debut Strength | Benchmarks | Status |")
    lines.append("|---|---|---|---|---|---|")
    for e in report.entries:
        lines.append(
            f"| {e.model_slug} | {e.organization} | {e.first_seen} "
            f"| {e.debut_strength} | {e.benchmark_count} | {e.status} |"
        )
    lines.append("")

    # Detail: best scores per model
    for e in report.entries:
        if e.best_scores:
            lines.append(f"### {e.model_slug}")
            lines.append("")
            lines.append("| Benchmark | Score |")
            lines.append("|---|---|")
            for bname, score in sorted(e.best_scores.items()):
                lines.append(f"| {bname} | {score} |")
            if e.xref_count:
                lines.append(f"\n*Confirmed by {e.xref_count} cross-reference(s)*")
            if e.insight_flags:
                lines.append(f"*Flags: {', '.join(e.insight_flags)}*")
            lines.append("")

    return "\n".join(lines)


def evolution_to_markdown(summaries: list[EvolutionSummary]) -> str:
    """Render evolution summaries as Markdown."""
    if not summaries:
        return "No benchmark evolution data.\n"

    lines = ["# Benchmark Evolution", ""]

    lines.append("| Benchmark | Leader | Top Score | Improvement | Rate/mo | Saturation | Models |")
    lines.append("|---|---|---|---|---|---|---|")
    for s in summaries:
        leader = s.current_leader or "—"
        top = f"{s.current_top_score}" if s.current_top_score is not None else "—"
        imp = f"{s.total_improvement:+.2f}" if s.total_improvement is not None else "—"
        rate = (
            f"{s.improvement_rate_per_month:+.2f}"
            if s.improvement_rate_per_month is not None
            else "—"
        )
        sat = f"{s.saturation_pct:.1f}%" if s.saturation_pct is not None else "—"
        lines.append(
            f"| {s.benchmark_name} | {leader} | {top} | {imp} | {rate} | {sat} "
            f"| {s.models_evaluated} |"
        )
    lines.append("")

    # Frontier detail per benchmark
    for s in summaries:
        if s.frontier:
            lines.append(f"### {s.benchmark_name} — Frontier Progression")
            lines.append("")
            lines.append("| Date | Model | Score |")
            lines.append("|---|---|---|")
            for f in s.frontier:
                lines.append(f"| {f.date} | {f.model_slug} | {f.score} |")
            lines.append("")

    return "\n".join(lines)


def capability_to_markdown(profile: CapabilityProfile) -> str:
    """Render a capability profile as Markdown."""
    lines = [
        f"# Capability Profile: {profile.model_slug}",
        "",
        f"**Organization:** {profile.organization}",
        f"**Benchmarks evaluated:** {profile.benchmark_count}",
        f"**Composite score:** {profile.composite_score:.1f}",
        "",
    ]

    if not profile.percentiles:
        lines.append("No benchmark data available.\n")
        return "\n".join(lines)

    lines.append("| Benchmark | Raw Score | Percentile | Models |")
    lines.append("|---|---|---|---|")
    for p in sorted(profile.percentiles, key=lambda x: -x.percentile_rank):
        raw = f"{p.raw_score}" if p.raw_score is not None else "—"
        lines.append(
            f"| {p.benchmark_variant} | {raw} | {p.percentile_rank:.1f}% "
            f"| {p.models_in_benchmark} |"
        )
    lines.append("")

    return "\n".join(lines)


def landscape_to_markdown(report: LandscapeReport) -> str:
    """Render a competitive landscape report as Markdown."""
    lines = [
        "# Competitive Landscape",
        "",
        f"**Window:** {report.window_days} days ({report.window_start} to {report.window_end})",
        "",
    ]

    if not report.entries:
        lines.append("No active organizations found.\n")
        return "\n".join(lines)

    lines.append("| Org | Models | New | Benchmarks | Best Score | Pricing | Trend |")
    lines.append("|---|---|---|---|---|---|---|")
    for e in report.entries:
        best = f"{e.best_result_score} ({e.best_result_benchmark})" if e.best_result_score else "—"
        price = f"{e.pricing_events}"
        if e.has_price_drop:
            price += " (drop)"
        lines.append(
            f"| {e.organization} | {e.total_models} | {e.new_models} "
            f"| {e.benchmark_breadth} | {best} | {price} | {e.trend} |"
        )
    lines.append("")

    return "\n".join(lines)
