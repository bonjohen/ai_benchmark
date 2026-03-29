"""Tests for analysis result dataclasses."""

from __future__ import annotations

from dataclasses import asdict

from ai_benchmark.analysis.types import (
    ActivityTimeline,
    BenchmarkDataPoint,
    CompetitiveCluster,
    DigestReport,
    Leaderboard,
    ModelComparisonMatrix,
    ModelProfile,
    ModelSummary,
    PaperCitationEntry,
    PaperProductLink,
    ResearchTrends,
    TimelineEntry,
)


def test_model_summary_creation():
    s = ModelSummary(
        model_slug="gpt-5",
        organization="OpenAI",
        first_seen="2026-03-15",
        latest_activity="2026-03-20",
        event_count=5,
        status="active",
    )
    assert s.model_slug == "gpt-5"
    assert s.status == "active"


def test_timeline_entry_creation():
    e = TimelineEntry(
        date="2026-03-15",
        event_type="model_release",
        title="GPT-5 Released",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
        event_id=1,
    )
    assert e.event_type == "model_release"
    assert e.event_id == 1


def test_benchmark_data_point():
    p = BenchmarkDataPoint(
        model_slug="gpt-5",
        score=72.3,
        date="2026-03-17",
        source_name="SWE-bench team",
        benchmark_variant="SWE-bench Verified",
    )
    assert p.score == 72.3


def test_benchmark_data_point_none_score():
    p = BenchmarkDataPoint(
        model_slug="gpt-5",
        score=None,
        date="2026-03-17",
        source_name="Unknown",
        benchmark_variant="LiveBench",
    )
    assert p.score is None


def test_model_profile_creation():
    profile = ModelProfile(
        model_slug="gpt-5",
        organization="OpenAI",
        first_seen="2026-03-15",
        latest_activity="2026-03-20",
        status="active",
        milestones=[],
        claim_summary={"confirmed": 2, "unconfirmed": 1, "conflicted": 0},
        benchmark_scores=[],
        related_models=[],
    )
    assert profile.claim_summary["confirmed"] == 2


def test_model_comparison_matrix():
    m = ModelComparisonMatrix(model_slugs=["gpt-5", "claude-4"], profiles={})
    assert len(m.model_slugs) == 2


def test_leaderboard_creation():
    lb = Leaderboard(
        benchmark_name="SWE-bench Verified",
        as_of="2026-03-29",
        entries=[
            BenchmarkDataPoint("gpt-5", 72.3, "2026-03-17", "SWE-bench", "SWE-bench Verified"),
        ],
    )
    assert len(lb.entries) == 1
    assert lb.entries[0].score == 72.3


def test_competitive_cluster():
    c = CompetitiveCluster(
        start_date="2026-03-15",
        end_date="2026-03-21",
        event_type="model_release",
        organizations=["OpenAI", "Anthropic"],
        event_count=3,
        event_ids=[1, 2, 3],
    )
    assert len(c.organizations) == 2


def test_activity_timeline():
    t = ActivityTimeline(
        window_start="2026-03-01",
        window_end="2026-03-29",
        org_activities=[],
        clusters=[],
    )
    assert t.window_start == "2026-03-01"


def test_research_trends():
    r = ResearchTrends(
        window_days=90,
        total_papers=100,
        promoted_count=30,
        rejected_count=50,
        pending_count=20,
        citation_leaders=[],
        topic_counts={"benchmark": 15, "llm": 40},
        paper_product_links=[],
    )
    assert r.total_papers == 100
    assert r.topic_counts["llm"] == 40


def test_digest_report_defaults():
    d = DigestReport(period_start="2026-03-22", period_end="2026-03-29")
    assert d.headline_insights == []
    assert d.model_updates == []
    assert d.stats == {}
    assert d.competitive_overview is None
    assert d.research_highlights is None


def test_dataclass_to_dict():
    s = ModelSummary("gpt-5", "OpenAI", "2026-03-15", "2026-03-20", 5, "active")
    d = asdict(s)
    assert d["model_slug"] == "gpt-5"
    assert isinstance(d, dict)


def test_paper_citation_entry():
    p = PaperCitationEntry(
        title="Test Paper",
        arxiv_id="2026.12345",
        citation_count=500,
        venue="NeurIPS",
        enriched_at="2026-03-01",
    )
    assert p.citation_count == 500


def test_paper_product_link():
    link = PaperProductLink(
        paper_title="Scaling Laws",
        paper_arxiv_id="2001.08361",
        model_slug="gpt-5",
        organization="OpenAI",
        lag_days=45,
    )
    assert link.lag_days == 45
