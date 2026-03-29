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
    spotlight_models: list[SpotlightEntry] = field(default_factory=list)
    evolution_highlights: list[EvolutionSummary] = field(default_factory=list)


# --- Presentation Layer Dataclasses ---


@dataclass
class SpotlightEntry:
    """A new model with benchmark performance context."""

    model_slug: str
    organization: str
    first_seen: str
    status: str
    benchmark_count: int
    best_scores: dict[str, float] = field(default_factory=dict)
    debut_strength: int = 0
    xref_count: int = 0
    insight_flags: list[str] = field(default_factory=list)


@dataclass
class SpotlightReport:
    """New model spotlight for a time window."""

    window_days: int
    cutoff_date: str
    total_new_models: int
    entries: list[SpotlightEntry] = field(default_factory=list)


@dataclass
class FrontierEntry:
    """A record-breaking score in a benchmark's history."""

    date: str
    model_slug: str
    score: float


@dataclass
class EvolutionSummary:
    """Temporal aggregate statistics for a benchmark."""

    benchmark_name: str
    window_days: int
    total_improvement: float | None = None
    improvement_rate_per_month: float | None = None
    current_leader: str | None = None
    current_top_score: float | None = None
    gap_to_second: float | None = None
    models_evaluated: int = 0
    saturation_pct: float | None = None
    last_record_date: str | None = None
    frontier: list[FrontierEntry] = field(default_factory=list)


@dataclass
class BenchmarkPercentile:
    """A model's normalized score on one benchmark."""

    benchmark_variant: str
    raw_score: float | None
    percentile_rank: float
    models_in_benchmark: int


@dataclass
class CapabilityProfile:
    """Cross-benchmark capability profile for one model."""

    model_slug: str
    organization: str
    benchmark_count: int
    percentiles: list[BenchmarkPercentile] = field(default_factory=list)
    composite_score: float = 0.0


@dataclass
class OrgLandscapeEntry:
    """Competitive landscape entry for one organization."""

    organization: str
    total_models: int
    new_models: int
    active_model_slugs: list[str] = field(default_factory=list)
    benchmark_breadth: int = 0
    avg_percentile: float | None = None
    best_result_model: str | None = None
    best_result_benchmark: str | None = None
    best_result_score: float | None = None
    pricing_events: int = 0
    has_price_drop: bool = False
    cluster_count: int = 0
    trend: str = "stable"


@dataclass
class LandscapeReport:
    """Competitive landscape for a time window."""

    window_days: int
    window_start: str
    window_end: str
    entries: list[OrgLandscapeEntry] = field(default_factory=list)


@dataclass
class CitationVelocityEntry:
    """Paper ranked by citation velocity."""

    title: str
    arxiv_id: str | None
    citation_count: int
    velocity_per_week: float
    venue: str | None


@dataclass
class TopicTrend:
    """Topic frequency trend across a split window."""

    topic: str
    total_count: int
    recent_count: int
    earlier_count: int
    direction: str  # "rising" | "falling" | "stable"


@dataclass
class ResearchPipelineReport:
    """Research-to-product pipeline intelligence."""

    window_days: int
    velocity_leaders: list[CitationVelocityEntry] = field(default_factory=list)
    topic_trends: list[TopicTrend] = field(default_factory=list)
    paper_product_links: list[PaperProductLink] = field(default_factory=list)
    predictive_signals: list[CitationVelocityEntry] = field(default_factory=list)


@dataclass
class ModelVerification:
    """Verification depth for one model."""

    model_slug: str
    organization: str
    total_claims: int
    confirmed_pct: float
    conflicted_pct: float
    source_count: int
    highest_confidence_tier: str
    xref_confirms_count: int


@dataclass
class BenchmarkVerification:
    """Verification summary for one benchmark variant."""

    benchmark_variant: str
    source_count: int
    has_conflicts: bool
    score_variance: float | None


@dataclass
class VerificationReport:
    """Claim verification dashboard."""

    total_events: int
    total_claims: int
    confirmation_rate: float
    conflict_rate: float
    tier_distribution: dict[str, int] = field(default_factory=dict)
    model_verifications: list[ModelVerification] = field(default_factory=list)
    benchmark_verifications: list[BenchmarkVerification] = field(default_factory=list)


@dataclass
class CorrelationEntry:
    """Pairwise benchmark correlation."""

    benchmark_a: str
    benchmark_b: str
    correlation: float
    overlap_count: int
    label: str  # "redundant" | "similar" | "moderate" | "distinct" | "independent"


@dataclass
class CorrelationMatrix:
    """Benchmark correlation matrix."""

    min_overlap: int
    benchmark_count: int
    entries: list[CorrelationEntry] = field(default_factory=list)
    clusters: list[list[str]] = field(default_factory=list)
