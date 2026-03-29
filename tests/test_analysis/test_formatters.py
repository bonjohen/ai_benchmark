"""Tests for analysis formatters (JSON, Markdown, CSV)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from ai_benchmark.analysis.formatters.csv_export import (
    evolution_to_csv,
    insights_to_csv,
    leaderboard_to_csv,
    models_to_csv,
    spotlight_to_csv,
)
from ai_benchmark.analysis.formatters.json_export import to_json
from ai_benchmark.analysis.formatters.markdown import (
    activity_timeline_to_markdown,
    capability_to_markdown,
    evolution_to_markdown,
    insights_to_markdown,
    landscape_to_markdown,
    leaderboard_to_markdown,
    model_list_to_markdown,
    model_profile_to_markdown,
    research_pipeline_to_markdown,
    research_trends_to_markdown,
    spotlight_to_markdown,
)
from ai_benchmark.analysis.models import AnalysisInsight
from ai_benchmark.analysis.types import (
    ActivityTimeline,
    BenchmarkDataPoint,
    BenchmarkPercentile,
    CapabilityProfile,
    CitationVelocityEntry,
    CompetitiveCluster,
    EvolutionSummary,
    FrontierEntry,
    LandscapeReport,
    Leaderboard,
    ModelProfile,
    ModelSummary,
    OrgActivity,
    OrgLandscapeEntry,
    PaperCitationEntry,
    PaperProductLink,
    ResearchPipelineReport,
    ResearchTrends,
    SpotlightEntry,
    SpotlightReport,
    TimelineEntry,
    TopicTrend,
)


def _make_models():
    return [
        ModelSummary("gpt-5", "OpenAI", "2026-03-15", "2026-03-17", 3, "active"),
        ModelSummary("claude-4", "Anthropic", "2026-03-01", "2026-03-10", 2, "active"),
    ]


def _make_profile():
    return ModelProfile(
        model_slug="gpt-5",
        organization="OpenAI",
        first_seen="2026-03-15",
        latest_activity="2026-03-17",
        status="active",
        milestones=[
            TimelineEntry(
                "2026-03-15",
                "model_release",
                "GPT-5 Released",
                "official_self_report",
                "confirmed",
                1,
            ),
        ],
        claim_summary={"confirmed": 3, "unconfirmed": 1},
        benchmark_scores=[
            BenchmarkDataPoint("gpt-5", 72.3, "2026-03-17", "OpenAI", "SWE-bench Verified"),
        ],
        related_models=["gpt-4o", "gpt-4o-mini"],
    )


def _make_leaderboard():
    return Leaderboard(
        benchmark_name="SWE-bench Verified",
        as_of="2026-03-20",
        entries=[
            BenchmarkDataPoint("gpt-5", 72.3, "2026-03-17", "OpenAI", "SWE-bench Verified"),
            BenchmarkDataPoint("claude-4", 68.1, "2026-03-10", "Anthropic", "SWE-bench Verified"),
        ],
    )


def _make_insights():
    return [
        AnalysisInsight(
            id=1,
            insight_type="new_model",
            severity="notable",
            title="New model: GPT-5",
            description="OpenAI released GPT-5",
            related_model_slug="gpt-5",
            related_org="OpenAI",
            detected_at=datetime(2026, 3, 15, tzinfo=UTC),
        ),
        AnalysisInsight(
            id=2,
            insight_type="price_drop",
            severity="info",
            title="Price reduction",
            description="GPT-5 prices dropped 20%",
            related_model_slug="gpt-5",
            related_org=None,
            detected_at=datetime(2026, 3, 16, tzinfo=UTC),
        ),
    ]


# --- JSON ---


def test_to_json_dataclass():
    """to_json serializes a dataclass to JSON."""
    model = _make_models()[0]
    result = json.loads(to_json(model))
    assert result["model_slug"] == "gpt-5"
    assert result["event_count"] == 3


def test_to_json_list():
    """to_json serializes a list of dataclasses."""
    models = _make_models()
    result = json.loads(to_json(models))
    assert isinstance(result, list)
    assert len(result) == 2


def test_to_json_dict():
    """to_json serializes a plain dict."""
    data = {"key": "value", "count": 42}
    result = json.loads(to_json(data))
    assert result == data


def test_to_json_indent():
    """to_json respects indent parameter."""
    data = {"a": 1}
    compact = to_json(data, indent=0)
    assert "\n" not in compact or "  " not in compact


# --- Markdown: model list ---


def test_model_list_to_markdown_header():
    """Model list markdown starts with header and table."""
    md = model_list_to_markdown(_make_models())
    assert "# Tracked Models" in md
    assert "| Model |" in md


def test_model_list_to_markdown_rows():
    """Model list markdown includes all models."""
    md = model_list_to_markdown(_make_models())
    assert "gpt-5" in md
    assert "claude-4" in md
    assert "Anthropic" in md


def test_model_list_to_markdown_empty():
    """Empty model list produces a message."""
    md = model_list_to_markdown([])
    assert "No tracked models" in md


# --- Markdown: model profile ---


def test_model_profile_to_markdown_header():
    """Model profile markdown starts with model slug as header."""
    md = model_profile_to_markdown(_make_profile())
    assert "# gpt-5" in md
    assert "**Organization:** OpenAI" in md


def test_model_profile_to_markdown_sections():
    """Model profile markdown includes claims, timeline, benchmarks, related."""
    md = model_profile_to_markdown(_make_profile())
    assert "## Claims" in md
    assert "## Timeline" in md
    assert "## Benchmark Scores" in md
    assert "## Related Models" in md


def test_model_profile_to_markdown_benchmark_data():
    """Benchmark table includes score and variant."""
    md = model_profile_to_markdown(_make_profile())
    assert "SWE-bench Verified" in md
    assert "72.3" in md


# --- Markdown: leaderboard ---


def test_leaderboard_to_markdown_header():
    """Leaderboard markdown includes benchmark name."""
    md = leaderboard_to_markdown(_make_leaderboard())
    assert "# SWE-bench Verified" in md
    assert "**As of:** 2026-03-20" in md


def test_leaderboard_to_markdown_rankings():
    """Leaderboard entries are ranked."""
    md = leaderboard_to_markdown(_make_leaderboard())
    lines = md.split("\n")
    data_lines = [line for line in lines if "gpt-5" in line or "claude-4" in line]
    assert len(data_lines) == 2
    assert "| 1 |" in md  # gpt-5 is rank 1
    assert "| 2 |" in md  # claude-4 is rank 2


def test_leaderboard_to_markdown_empty():
    """Empty leaderboard shows message."""
    lb = Leaderboard("Test", "2026-03-20", [])
    md = leaderboard_to_markdown(lb)
    assert "No entries found" in md


# --- Markdown: activity timeline ---


def test_activity_timeline_to_markdown():
    """Activity timeline markdown renders org activities and clusters."""
    timeline = ActivityTimeline(
        window_start="2026-03-01",
        window_end="2026-03-30",
        org_activities=[
            OrgActivity("OpenAI", {"model_release": 2}, ["gpt-5", "gpt-4o"], 2),
        ],
        clusters=[
            CompetitiveCluster(
                "2026-03-15", "2026-03-17", "model_release", ["OpenAI", "Google"], 3, [1, 2, 3]
            ),
        ],
    )
    md = activity_timeline_to_markdown(timeline)
    assert "# Competitive Activity" in md
    assert "OpenAI" in md
    assert "## Competitive Clusters" in md


# --- Markdown: research trends ---


def test_research_trends_to_markdown():
    """Research trends markdown renders citation leaders and topics."""
    trends = ResearchTrends(
        window_days=90,
        total_papers=50,
        promoted_count=10,
        rejected_count=5,
        pending_count=35,
        citation_leaders=[
            PaperCitationEntry("Scaling Laws", "2001.08361", 1500, "NeurIPS", "2026-01-01"),
        ],
        topic_counts={"llm": 20, "safety": 10},
        paper_product_links=[
            PaperProductLink("Scaling Laws", "2001.08361", "gpt-5", "OpenAI", 30),
        ],
    )
    md = research_trends_to_markdown(trends)
    assert "# Research Pulse" in md
    assert "Scaling Laws" in md
    assert "## Trending Topics" in md


# --- Markdown: insights ---


def test_insights_to_markdown():
    """Insights markdown renders sorted by severity."""
    md = insights_to_markdown(_make_insights())
    assert "# Analysis Insights" in md
    assert "New model: GPT-5" in md
    assert "Price reduction" in md


def test_insights_to_markdown_empty():
    """Empty insights shows message."""
    md = insights_to_markdown([])
    assert "No insights detected" in md


# --- CSV: models ---


def test_models_to_csv_header():
    """Models CSV starts with header row."""
    result = models_to_csv(_make_models())
    reader = csv.reader(io.StringIO(result))
    header = next(reader)
    assert "model_slug" in header
    assert "organization" in header


def test_models_to_csv_rows():
    """Models CSV includes all models."""
    result = models_to_csv(_make_models())
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 3  # header + 2 data rows
    assert rows[1][0] == "gpt-5"
    assert rows[2][0] == "claude-4"


# --- CSV: leaderboard ---


def test_leaderboard_to_csv_header():
    """Leaderboard CSV has correct header."""
    result = leaderboard_to_csv(_make_leaderboard())
    reader = csv.reader(io.StringIO(result))
    header = next(reader)
    assert "rank" in header
    assert "score" in header


def test_leaderboard_to_csv_rows():
    """Leaderboard CSV includes ranked entries."""
    result = leaderboard_to_csv(_make_leaderboard())
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 3  # header + 2 entries
    assert rows[1][0] == "1"  # rank 1
    assert rows[1][2] == "72.3"  # score


# --- CSV: insights ---


def test_insights_to_csv_header():
    """Insights CSV has correct header."""
    result = insights_to_csv(_make_insights())
    reader = csv.reader(io.StringIO(result))
    header = next(reader)
    assert "insight_type" in header
    assert "severity" in header


def test_insights_to_csv_rows():
    """Insights CSV includes all insights."""
    result = insights_to_csv(_make_insights())
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 3  # header + 2 insights
    assert rows[1][1] == "new_model"


# --- Markdown: spotlight ---


def _make_spotlight():
    return SpotlightReport(
        window_days=30,
        cutoff_date="2026-03-01",
        total_new_models=2,
        entries=[
            SpotlightEntry(
                model_slug="gpt-5",
                organization="OpenAI",
                first_seen="2026-03-15",
                status="active",
                benchmark_count=2,
                best_scores={"SWE-bench Verified": 92.3, "MMLU": 95.1},
                debut_strength=2,
                xref_count=1,
                insight_flags=["new_model"],
            ),
            SpotlightEntry(
                model_slug="claude-4",
                organization="Anthropic",
                first_seen="2026-03-16",
                status="active",
                benchmark_count=1,
                best_scores={"SWE-bench Verified": 89.7},
                debut_strength=0,
                xref_count=0,
                insight_flags=[],
            ),
        ],
    )


def test_spotlight_to_markdown_header():
    """Spotlight markdown includes title and window."""
    md = spotlight_to_markdown(_make_spotlight())
    assert "# New Model Spotlight" in md
    assert "30 days" in md


def test_spotlight_to_markdown_entries():
    """Spotlight markdown shows model entries."""
    md = spotlight_to_markdown(_make_spotlight())
    assert "gpt-5" in md
    assert "claude-4" in md
    assert "92.3" in md


def test_spotlight_to_csv_rows():
    """Spotlight CSV has correct row count."""
    result = spotlight_to_csv(_make_spotlight())
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 3  # header + 2 entries
    assert rows[1][0] == "gpt-5"


# --- Markdown: evolution ---


def _make_evolution():
    return [
        EvolutionSummary(
            benchmark_name="SWE-bench Verified",
            window_days=180,
            total_improvement=20.8,
            improvement_rate_per_month=3.47,
            current_leader="gpt-5",
            current_top_score=92.3,
            gap_to_second=2.6,
            models_evaluated=3,
            saturation_pct=92.3,
            last_record_date="2026-03-17",
            frontier=[
                FrontierEntry("2026-01-15", "gpt-4o", 71.5),
                FrontierEntry("2026-03-17", "gpt-5", 92.3),
            ],
        ),
    ]


def test_evolution_to_markdown_header():
    """Evolution markdown includes title and table."""
    md = evolution_to_markdown(_make_evolution())
    assert "# Benchmark Evolution" in md
    assert "SWE-bench Verified" in md


def test_evolution_to_markdown_frontier():
    """Evolution markdown shows frontier progression."""
    md = evolution_to_markdown(_make_evolution())
    assert "Frontier Progression" in md
    assert "gpt-4o" in md
    assert "71.5" in md


def test_evolution_to_csv_rows():
    """Evolution CSV has correct row count."""
    result = evolution_to_csv(_make_evolution())
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 2  # header + 1 benchmark
    assert rows[1][0] == "SWE-bench Verified"


# --- Markdown: capability ---


def _make_capability():
    return CapabilityProfile(
        model_slug="gpt-5",
        organization="OpenAI",
        benchmark_count=2,
        percentiles=[
            BenchmarkPercentile("SWE-bench Verified", 92.3, 100.0, 3),
            BenchmarkPercentile("MMLU", 95.1, 100.0, 2),
        ],
        composite_score=100.0,
    )


def test_capability_to_markdown_header():
    """Capability markdown includes model name and composite."""
    md = capability_to_markdown(_make_capability())
    assert "gpt-5" in md
    assert "100.0" in md


def test_capability_to_markdown_percentiles():
    """Capability markdown shows benchmark percentiles."""
    md = capability_to_markdown(_make_capability())
    assert "SWE-bench Verified" in md
    assert "92.3" in md


# --- Markdown: landscape ---


def _make_landscape():
    return LandscapeReport(
        window_days=30,
        window_start="2026-03-01",
        window_end="2026-03-29",
        entries=[
            OrgLandscapeEntry(
                organization="OpenAI",
                total_models=3,
                new_models=1,
                active_model_slugs=["gpt-5"],
                benchmark_breadth=2,
                best_result_model="gpt-5",
                best_result_benchmark="MMLU",
                best_result_score=95.1,
                pricing_events=1,
                has_price_drop=True,
                cluster_count=1,
                trend="up",
            ),
        ],
    )


def test_landscape_to_markdown_header():
    """Landscape markdown includes title and window."""
    md = landscape_to_markdown(_make_landscape())
    assert "# Competitive Landscape" in md
    assert "30 days" in md


def test_landscape_to_markdown_entries():
    """Landscape markdown shows org entries."""
    md = landscape_to_markdown(_make_landscape())
    assert "OpenAI" in md
    assert "95.1" in md
    assert "drop" in md


# --- Markdown: research pipeline ---


def _make_research_pipeline():
    return ResearchPipelineReport(
        window_days=90,
        velocity_leaders=[
            CitationVelocityEntry("Scaling Laws", "2001.08361", 1500, 350.0, "NeurIPS"),
            CitationVelocityEntry("Constitutional AI", "2212.08073", 800, 120.0, "ICML"),
        ],
        topic_trends=[
            TopicTrend("llm", 20, 12, 8, "rising"),
            TopicTrend("safety", 10, 4, 6, "falling"),
        ],
        paper_product_links=[
            PaperProductLink("Scaling Laws", "2001.08361", "gpt-5", "OpenAI", 30),
        ],
        predictive_signals=[
            CitationVelocityEntry("Scaling Laws", "2001.08361", 1500, 350.0, "NeurIPS"),
        ],
    )


def test_research_pipeline_to_markdown_header():
    """Research pipeline markdown includes title and window."""
    md = research_pipeline_to_markdown(_make_research_pipeline())
    assert "# Research-to-Product Pipeline" in md
    assert "90 days" in md


def test_research_pipeline_to_markdown_velocity():
    """Research pipeline markdown shows velocity leaders."""
    md = research_pipeline_to_markdown(_make_research_pipeline())
    assert "Citation Velocity Leaders" in md
    assert "Scaling Laws" in md
    assert "350.00" in md


def test_research_pipeline_to_markdown_topics():
    """Research pipeline markdown shows topic trends."""
    md = research_pipeline_to_markdown(_make_research_pipeline())
    assert "Topic Trends" in md
    assert "llm" in md
    assert "rising" in md
