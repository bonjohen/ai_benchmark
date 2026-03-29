"""Result dataclasses for analysis services. Pure data containers, no DB dependency."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelSummary:
    """Lightweight model overview for listings."""

    model_slug: str
    organization: str
    first_seen: str | None
    latest_activity: str | None
    event_count: int
    status: str  # active | deprecated | announced


@dataclass
class TimelineEntry:
    """Single event in a model's timeline."""

    date: str
    event_type: str
    title: str
    confidence_tier: str
    confirmation_status: str
    event_id: int


@dataclass
class BenchmarkDataPoint:
    """Single benchmark score observation."""

    model_slug: str
    score: float | None
    date: str
    source_name: str
    benchmark_variant: str


@dataclass
class ModelProfile:
    """Complete lifecycle for one model."""

    model_slug: str
    organization: str
    first_seen: str | None
    latest_activity: str | None
    status: str
    milestones: list[TimelineEntry]
    claim_summary: dict[str, int]
    benchmark_scores: list[BenchmarkDataPoint]
    related_models: list[str]


@dataclass
class ModelComparisonMatrix:
    """Side-by-side comparison of multiple models."""

    model_slugs: list[str]
    profiles: dict[str, ModelProfile]


@dataclass
class BenchmarkSummary:
    """Lightweight benchmark overview for listings."""

    benchmark_name: str
    entry_count: int
    latest_date: str | None
    top_model: str | None
    top_score: float | None


@dataclass
class Leaderboard:
    """Point-in-time benchmark leaderboard."""

    benchmark_name: str
    as_of: str
    entries: list[BenchmarkDataPoint]


@dataclass
class OrgActivity:
    """Per-organization activity summary."""

    organization: str
    event_counts: dict[str, int]
    active_models: list[str]
    total_events: int


@dataclass
class CompetitiveCluster:
    """Time window where multiple orgs had similar events."""

    start_date: str
    end_date: str
    event_type: str
    organizations: list[str]
    event_count: int
    event_ids: list[int]


@dataclass
class ActivityTimeline:
    """Cross-vendor activity for a time window."""

    window_start: str
    window_end: str
    org_activities: list[OrgActivity]
    clusters: list[CompetitiveCluster]


@dataclass
class PaperCitationEntry:
    """Paper ranked by citation count."""

    title: str
    arxiv_id: str | None
    citation_count: int
    venue: str | None
    enriched_at: str


@dataclass
class PaperProductLink:
    """Match between a research paper and a product release."""

    paper_title: str
    paper_arxiv_id: str | None
    model_slug: str
    organization: str
    lag_days: int


@dataclass
class ResearchTrends:
    """Research pulse for a time window."""

    window_days: int
    total_papers: int
    promoted_count: int
    rejected_count: int
    pending_count: int
    citation_leaders: list[PaperCitationEntry]
    topic_counts: dict[str, int]
    paper_product_links: list[PaperProductLink]


@dataclass
class DigestReport:
    """Full periodic intelligence digest."""

    period_start: str
    period_end: str
    headline_insights: list[dict] = field(default_factory=list)
    model_updates: list[ModelSummary] = field(default_factory=list)
    benchmark_movements: list[BenchmarkDataPoint] = field(default_factory=list)
    competitive_overview: ActivityTimeline | None = None
    research_highlights: ResearchTrends | None = None
    stats: dict[str, int] = field(default_factory=dict)
