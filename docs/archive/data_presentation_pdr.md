# Physical Design Requirements: Data Presentation & Intelligence Products

**Source document:** `docs/data_presentation_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-29 02:15 PM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| `list_tracked_models()` | `analysis/services/model_lifecycle.py` | Spotlight: filter by `first_seen` date to find new models |
| `build_model_profile()` | `analysis/services/model_lifecycle.py` | Capability: fetch per-model benchmark scores |
| `get_benchmark_leaderboard()` | `analysis/services/benchmark_trends.py` | Spotlight: compute top-3 rankings; Capability: percentile normalization |
| `get_benchmark_timeline()` | `analysis/services/benchmark_trends.py` | Evolution: source data for rate-of-improvement and frontier progression |
| `list_benchmarks()` | `analysis/services/benchmark_trends.py` | Evolution: enumerate all benchmark variants |
| `extract_benchmark_score()` | `analysis/services/benchmark_trends.py` | All products: 4-priority regex score extraction from `raw_content` |
| `get_activity_timeline()` | `analysis/services/competitive_intel.py` | Landscape: org activity + competitive clusters |
| `org_activity_summary()` | `analysis/services/competitive_intel.py` | Landscape: single-org breakdown |
| `get_research_trends()` | `analysis/services/research_pulse.py` | Research Pipeline: base paper counts and topic data |
| `detect_paper_to_product()` | `analysis/services/research_pulse.py` | Research Pipeline: paper-product links as training data |
| `get_citation_leaders()` | `analysis/services/research_pulse.py` | Research Pipeline: citation data for velocity computation |
| `detect_anomalies()` | `analysis/services/anomaly_detector.py` | Spotlight: anomaly flags per model |
| `get_recent_insights()` | `analysis/services/anomaly_detector.py` | Spotlight/Landscape: insight context |
| `generate_digest()` | `analysis/services/digest.py` | Digest integration: extend with spotlight + evolution |
| `AnalysisSnapshot` | `analysis/models.py` | All products: optional persistence of computed results |
| `AnalysisInsight` | `analysis/models.py` | Spotlight/Landscape: query existing insights |
| `to_json()` | `analysis/formatters/json_export.py` | All products: JSON output via `dataclasses.asdict()` |
| CLI pattern | `analysis/cli.py` | All products: `_get_analysis_engine()`, `@analyze_group.command()`, `asyncio.run(_run())` |
| API pattern | `analysis/api.py` | All products: `Depends(_get_session_dep())`, `_to_dict()` conversion |
| Test fixtures | `tests/test_analysis/conftest.py` | All tests: `db_session`, `sample_events`, `sample_claims`, `sample_enriched_papers` |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| None | All computation uses stdlib (`statistics`, `math`, `collections`) and existing SQLAlchemy/Click/FastAPI | N/A |

No new dependencies. Spearman correlation (Product 7) uses a manual rank-based computation or `statistics.correlation()` from Python 3.12+ stdlib. All other math is basic arithmetic.

### 1.3 Existing Data Tables Queried (Read-Only)

| Table | Key Columns Used | Products |
|---|---|---|
| `event_records` | `model_slug`, `organization`, `event_type`, `benchmark_variant`, `evaluation_conditions`, `version`, `observed_at`, `raw_content`, `published_date` | All 7 products |
| `claim_records` | `event_id`, `source_type`, `source_name`, `confidence_tier`, `confirmation_status`, `claim_text` | Verification (6), Spotlight (1) |
| `cross_references` | `record_a_id`, `record_b_id`, `relationship_type` | Verification (6), Spotlight (1) |
| `candidate_papers` | `status`, `discovered_at` | Research Pipeline (5) |
| `enriched_papers` | `title`, `authors`, `arxiv_id`, `citation_count`, `venue`, `relevance_tags`, `enriched_at` | Research Pipeline (5) |
| `analysis_insights` | `insight_type`, `severity`, `related_model_slug`, `related_org` | Spotlight (1), Landscape (4) |

## 2. Package Layout

No new packages or directories. All new code goes into the existing `ai_benchmark/analysis/` package:

```
ai_benchmark/analysis/
  types.py                     # +7 new dataclasses (extend existing 15)
  services/
    spotlight.py               # NEW — Product 1: New Model Spotlight
    evolution.py               # NEW — Product 2: Benchmark Evolution
    capability.py              # NEW — Product 3: Cross-Benchmark Capability
    landscape.py               # NEW — Product 4: Competitive Landscape
    research_pipeline.py       # NEW — Product 5: Research-to-Product Pipeline
    verification.py            # NEW — Product 6: Claim Verification
    correlation.py             # NEW — Product 7: Benchmark Correlation
    digest.py                  # MODIFY — extend with spotlight + evolution
  formatters/
    markdown.py                # MODIFY — +7 new renderers
    csv_export.py              # MODIFY — +4 new CSV exporters
  cli.py                       # MODIFY — +7 new subcommands
  api.py                       # MODIFY — +9 new endpoints

tests/test_analysis/
  test_spotlight.py            # NEW
  test_evolution.py            # NEW
  test_capability.py           # NEW
  test_landscape.py            # NEW
  test_research_pipeline.py    # NEW
  test_verification.py         # NEW
  test_correlation.py          # NEW
  conftest.py                  # MODIFY — extend fixtures for new products
```

## 3. Data Model

### 3.1 New Dataclasses (in `types.py`)

No new ORM tables. All new types are pure dataclasses.

**`SpotlightEntry`**
```python
@dataclass
class SpotlightEntry:
    model_slug: str
    organization: str
    first_seen: str
    status: str
    benchmark_count: int                           # benchmarks where model has scores
    best_scores: dict[str, float]                  # benchmark_variant -> best score
    debut_strength: int                            # count of benchmarks where model is top-3
    xref_count: int                                # CrossReference "confirms" count
    insight_flags: list[str]                       # insight_types from AnalysisInsight
```

**`SpotlightReport`**
```python
@dataclass
class SpotlightReport:
    window_days: int
    cutoff_date: str
    total_new_models: int
    entries: list[SpotlightEntry]                  # sorted by debut_strength desc
```

**`FrontierEntry`**
```python
@dataclass
class FrontierEntry:
    date: str
    model_slug: str
    score: float
```

**`EvolutionSummary`**
```python
@dataclass
class EvolutionSummary:
    benchmark_name: str
    window_days: int
    total_improvement: float | None                # latest top - earliest top
    improvement_rate_per_month: float | None        # score gain / months in window
    current_leader: str | None                     # model_slug
    current_top_score: float | None
    gap_to_second: float | None
    models_evaluated: int
    saturation_pct: float | None                   # top_score / ceiling * 100, None if no ceiling
    last_record_date: str | None
    frontier: list[FrontierEntry]                  # chronological record-breakers
```

**`BenchmarkPercentile`**
```python
@dataclass
class BenchmarkPercentile:
    benchmark_variant: str
    raw_score: float | None
    percentile_rank: float                         # 0.0 to 100.0
    models_in_benchmark: int                       # total models with scores on this benchmark
```

**`CapabilityProfile`**
```python
@dataclass
class CapabilityProfile:
    model_slug: str
    organization: str
    benchmark_count: int
    percentiles: list[BenchmarkPercentile]
    composite_score: float                         # weighted average of percentile ranks
```

**`OrgLandscapeEntry`**
```python
@dataclass
class OrgLandscapeEntry:
    organization: str
    total_models: int
    new_models: int                                # first_seen in window
    active_model_slugs: list[str]
    benchmark_breadth: int                         # distinct benchmarks across org models
    avg_percentile: float | None                   # mean percentile rank across all org model-benchmark pairs
    best_result_model: str | None
    best_result_benchmark: str | None
    best_result_score: float | None
    pricing_events: int
    has_price_drop: bool
    cluster_count: int                             # competitive clusters participated in
    trend: str                                     # "up" | "down" | "stable"
```

**`LandscapeReport`**
```python
@dataclass
class LandscapeReport:
    window_days: int
    window_start: str
    window_end: str
    entries: list[OrgLandscapeEntry]               # sorted by avg_percentile desc
```

**`CitationVelocityEntry`**
```python
@dataclass
class CitationVelocityEntry:
    title: str
    arxiv_id: str | None
    citation_count: int
    velocity_per_week: float                       # citations / weeks since enriched_at
    venue: str | None
```

**`TopicTrend`**
```python
@dataclass
class TopicTrend:
    topic: str
    total_count: int
    recent_count: int                              # second half of window
    earlier_count: int                             # first half of window
    direction: str                                 # "rising" | "falling" | "stable"
```

**`ResearchPipelineReport`**
```python
@dataclass
class ResearchPipelineReport:
    window_days: int
    velocity_leaders: list[CitationVelocityEntry]
    topic_trends: list[TopicTrend]
    paper_product_links: list[PaperProductLink]    # reuse existing type
    predictive_signals: list[CitationVelocityEntry]  # high-velocity in historically productive topics
```

**`ModelVerification`**
```python
@dataclass
class ModelVerification:
    model_slug: str
    organization: str
    total_claims: int
    confirmed_pct: float
    conflicted_pct: float
    source_count: int                              # distinct source_name values
    highest_confidence_tier: str
    xref_confirms_count: int                       # CrossReference "confirms" relationships
```

**`BenchmarkVerification`**
```python
@dataclass
class BenchmarkVerification:
    benchmark_variant: str
    source_count: int
    has_conflicts: bool
    score_variance: float | None                   # variance across source scores
```

**`VerificationReport`**
```python
@dataclass
class VerificationReport:
    total_events: int
    total_claims: int
    confirmation_rate: float                       # % confirmed
    conflict_rate: float                           # % conflicted
    tier_distribution: dict[str, int]              # confidence_tier -> count
    model_verifications: list[ModelVerification]
    benchmark_verifications: list[BenchmarkVerification]
```

**`CorrelationEntry`**
```python
@dataclass
class CorrelationEntry:
    benchmark_a: str
    benchmark_b: str
    correlation: float                             # Spearman rank correlation coefficient
    overlap_count: int                             # models with scores on both
    label: str                                     # "redundant" | "similar" | "moderate" | "distinct" | "independent"
```

**`CorrelationMatrix`**
```python
@dataclass
class CorrelationMatrix:
    min_overlap: int
    benchmark_count: int
    entries: list[CorrelationEntry]                # sorted by abs(correlation) desc
    clusters: list[list[str]]                      # groups of highly-correlated benchmark names
```

### 3.2 Digest Extension

Extend the existing `DigestReport` dataclass with two optional fields:

```python
# Added to existing DigestReport
spotlight_models: list[SpotlightEntry] = field(default_factory=list)
evolution_highlights: list[EvolutionSummary] = field(default_factory=list)
```

## 4. Service Functions

### 4.1 Spotlight Service (`services/spotlight.py`)

```python
async def get_spotlight(
    session: AsyncSession,
    *,
    window_days: int = 30,
    min_benchmarks: int = 1,
    organization: str | None = None,
) -> SpotlightReport
```

**Algorithm:**
1. Call `list_tracked_models(session, organization=organization, limit=500)` to get all models
2. Filter to models where `first_seen >= cutoff_date`
3. For each new model, call `get_benchmark_leaderboard(session, benchmark_name)` for each known benchmark variant (from `list_benchmarks()`)
4. Compute `debut_strength`: count of benchmarks where the model's score places it in the top 3
5. Query `CrossReference` for `relationship_type='confirms'` involving events with `model_slug = slug`
6. Query `AnalysisInsight` for `related_model_slug = slug`
7. Filter out models with `benchmark_count < min_benchmarks`
8. Sort by `debut_strength` descending

**Existing functions called:** `list_tracked_models`, `list_benchmarks`, `get_benchmark_leaderboard`, `get_recent_insights`
**Direct queries:** CrossReference count per model

### 4.2 Evolution Service (`services/evolution.py`)

```python
async def get_benchmark_evolution(
    session: AsyncSession,
    *,
    benchmark_name: str | None = None,
    window_days: int = 180,
) -> list[EvolutionSummary]
```

**Algorithm:**
1. If `benchmark_name` is specified, operate on that single benchmark; otherwise call `list_benchmarks()` and iterate
2. For each benchmark, call `get_benchmark_timeline(session, benchmark_name)` for the full time series
3. Filter data points to the window
4. Compute `total_improvement`: latest top score minus earliest top score
5. Compute `improvement_rate_per_month`: total_improvement / (window_days / 30)
6. Compute `frontier`: iterate chronologically, keeping only data points that set a new all-time high
7. Compute `saturation_pct`: if scores are percentages (max <= 100), use ceiling=100; if Elo-like (1000-2000 range), None; otherwise ceiling = max_observed * 1.1
8. `gap_to_second`: difference between rank 1 and rank 2 scores in the most recent leaderboard

**Existing functions called:** `list_benchmarks`, `get_benchmark_timeline`, `get_benchmark_leaderboard`
**Direct queries:** None — all data comes from existing services

### 4.3 Capability Service (`services/capability.py`)

```python
async def get_capability_profile(
    session: AsyncSession,
    model_slug: str,
) -> CapabilityProfile | None

async def compare_capabilities(
    session: AsyncSession,
    model_slugs: list[str],
) -> list[CapabilityProfile]
```

**Algorithm:**
1. Call `build_model_profile(session, model_slug)` to get the model's benchmark_scores
2. For each `BenchmarkDataPoint` in `benchmark_scores`, collect the score
3. For each benchmark variant, call `get_benchmark_leaderboard()` to get all scores for that variant
4. Compute percentile rank: `(count of models with score < this model's score) / (total models - 1) * 100`
5. Compute `composite_score`: mean of percentile ranks (equal weight)
6. `compare_capabilities` calls `get_capability_profile` for each slug

**Existing functions called:** `build_model_profile`, `get_benchmark_leaderboard`
**Direct queries:** None

### 4.4 Landscape Service (`services/landscape.py`)

```python
async def get_landscape(
    session: AsyncSession,
    *,
    window_days: int = 30,
    organization: str | None = None,
) -> LandscapeReport
```

**Algorithm:**
1. Call `get_activity_timeline(session, window_days=window_days)` for org activities and clusters
2. For each org, call `list_tracked_models(session, organization=org_name)` and partition by `first_seen` in window
3. For each org's models, compute `avg_percentile` via the capability normalization logic (shared helper from capability service)
4. Find best single result per org: iterate model benchmark scores, take max
5. Count pricing events: filter `event_type == 'pricing_change'` from org events
6. Check `get_recent_insights(session, insight_type='price_drop')` filtered by `related_org`
7. Count cluster participations from the activity timeline clusters
8. Compute trend: compare org's event count in this window to the prior equivalent window

**Existing functions called:** `get_activity_timeline`, `list_tracked_models`, `get_recent_insights`
**Direct queries:** EventRecord count for prior window (trend computation)

### 4.5 Research Pipeline Service (`services/research_pipeline.py`)

```python
async def get_research_pipeline(
    session: AsyncSession,
    *,
    window_days: int = 90,
    min_citations: int = 0,
) -> ResearchPipelineReport
```

**Algorithm:**
1. Call `get_citation_leaders(session, limit=100)` for citation data
2. Compute velocity: `citation_count / max(1, weeks_since_enriched_at)` for each paper
3. Filter by `min_citations`
4. Call `_count_topics()` (private in research_pulse) — duplicate the logic or extract as shared helper for the two window halves to compute trend direction
5. Call `detect_paper_to_product(session)` for existing links
6. Identify productive topics: relevance_tags that appear on papers in the paper_product_links
7. Predictive signals: papers with velocity > median and relevance_tags overlapping productive topics

**Existing functions called:** `get_citation_leaders`, `detect_paper_to_product`
**Direct queries:** EnrichedPaper for velocity computation, relevance_tags for split-window trend

### 4.6 Verification Service (`services/verification.py`)

```python
async def get_verification_report(
    session: AsyncSession,
    *,
    organization: str | None = None,
    model_slug: str | None = None,
) -> VerificationReport
```

**Algorithm:**
1. Query all EventRecords (optionally filtered by organization or model_slug)
2. For each model_slug, join ClaimRecords via `event_id` and compute: total claims, confirmed/conflicted percentages, distinct source_name count, highest confidence_tier
3. Query CrossReference where `relationship_type = 'confirms'` for events of each model
4. For each benchmark_variant, collect scores from all sources, compute variance, check for conflicts
5. System-level: aggregate counts across all models

**Existing functions called:** None directly — queries collection tables
**Direct queries:** EventRecord, ClaimRecord (joined), CrossReference

### 4.7 Correlation Service (`services/correlation.py`)

```python
async def get_correlation_matrix(
    session: AsyncSession,
    *,
    min_overlap: int = 5,
) -> CorrelationMatrix
```

**Algorithm:**
1. Query all EventRecords where `benchmark_variant IS NOT NULL` and `raw_content IS NOT NULL`
2. For each event, extract score via `extract_benchmark_score()`
3. Build a matrix: `{model_slug: {benchmark_variant: score}}`
4. For each pair of benchmark variants, find models that have scores on both
5. If overlap >= `min_overlap`, compute Spearman rank correlation:
   - Rank scores within each benchmark
   - Compute Pearson correlation of ranks: `1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))`
6. Label: > 0.8 = "redundant", 0.6-0.8 = "similar", 0.3-0.6 = "moderate", 0.1-0.3 = "distinct", < 0.1 = "independent"
7. Cluster: groups of benchmarks where all pairwise correlations > 0.7

**Existing functions called:** `extract_benchmark_score`
**Direct queries:** EventRecord (benchmark_variant + raw_content)

## 5. CLI Commands

Seven new subcommands added to the existing `analyze_group` in `cli.py`. Each follows the identical pattern:

```python
@analyze_group.command("command-name")
@click.option("--format", "fmt", type=click.Choice([...]), default="text")
def command_name(fmt, ...):
    """Help text."""
    async def _run():
        engine = _get_analysis_engine()
        async with AsyncSession(engine) as session:
            result = await service_function(session, ...)
            # format and output
    asyncio.run(_run())
```

| Command | Options | Formats |
|---|---|---|
| `spotlight` | `--days 30`, `--min-benchmarks 1`, `--org ORG` | text, json, markdown, csv |
| `evolution` | `--benchmark NAME`, `--days 180` | text, json, markdown, csv |
| `capability` | `slug` (arg), `--compare slug2,slug3` | text, json, markdown |
| `landscape` | `--days 30`, `--org ORG` | text, json, markdown |
| `research-pipeline` | `--days 90` | text, json, markdown |
| `verification` | `--org ORG`, `--model SLUG` | text, json, markdown, csv |
| `correlations` | `--min-overlap 5` | text, json, csv |

## 6. API Endpoints

Nine new endpoints added to the existing router in `api.py`. Each follows the identical pattern:

```python
@router.get("/path")
async def endpoint_name(
    param: type = Query(default),
    session: AsyncSession = _session,  # noqa: B008
) -> dict | list:
    result = await service_function(session, ...)
    return _to_dict(result)
```

| Method | Path | Parameters | Returns |
|---|---|---|---|
| GET | `/spotlight` | `days: int = 30`, `min_benchmarks: int = 1`, `org: str \| None` | SpotlightReport dict |
| GET | `/evolution` | `benchmark: str \| None`, `days: int = 180` | list[EvolutionSummary] dicts |
| GET | `/capability/{slug}` | path: `slug` | CapabilityProfile dict |
| GET | `/capability` | `models: str` (comma-separated slugs) | list[CapabilityProfile] dicts |
| GET | `/landscape` | `days: int = 30`, `org: str \| None` | LandscapeReport dict |
| GET | `/research-pipeline` | `days: int = 90` | ResearchPipelineReport dict |
| GET | `/verification` | `org: str \| None`, `model: str \| None` | VerificationReport dict |
| GET | `/correlations` | `min_overlap: int = 5` | CorrelationMatrix dict |

## 7. Formatter Functions

### 7.1 Markdown (`formatters/markdown.py`)

| Function | Input Type |
|---|---|
| `spotlight_to_markdown(report: SpotlightReport)` | SpotlightReport |
| `evolution_to_markdown(summaries: list[EvolutionSummary])` | list[EvolutionSummary] |
| `capability_to_markdown(profile: CapabilityProfile)` | CapabilityProfile |
| `landscape_to_markdown(report: LandscapeReport)` | LandscapeReport |
| `research_pipeline_to_markdown(report: ResearchPipelineReport)` | ResearchPipelineReport |
| `verification_to_markdown(report: VerificationReport)` | VerificationReport |
| `correlation_to_markdown(matrix: CorrelationMatrix)` | CorrelationMatrix |

### 7.2 CSV (`formatters/csv_export.py`)

| Function | Input Type |
|---|---|
| `spotlight_to_csv(report: SpotlightReport)` | SpotlightReport |
| `evolution_to_csv(summaries: list[EvolutionSummary])` | list[EvolutionSummary] |
| `verification_to_csv(report: VerificationReport)` | VerificationReport |
| `correlation_to_csv(matrix: CorrelationMatrix)` | CorrelationMatrix |

### 7.3 JSON

Uses existing `to_json()` — no changes needed.

## 8. Digest Integration

Modify `services/digest.py`:

```python
# In generate_digest(), after existing service calls:
from .spotlight import get_spotlight
from .evolution import get_benchmark_evolution

spotlight = await get_spotlight(session, window_days=window_days, min_benchmarks=1)
evolution = await get_benchmark_evolution(session, window_days=window_days)
```

Extend `DigestReport` in `types.py`:
```python
spotlight_models: list[SpotlightEntry] = field(default_factory=list)
evolution_highlights: list[EvolutionSummary] = field(default_factory=list)
```

Extend `digest_to_markdown()` in `formatters/markdown.py` to render the new fields.

## 9. Test Plan

### 9.1 Test Fixtures (extend `conftest.py`)

Add benchmark events with extractable scores to `sample_events`:
- GPT-5 on SWE-bench: `raw_content="Scored 92.3% on SWE-bench Verified"`, `benchmark_variant="SWE-bench Verified"`
- GPT-5 on MMLU: `raw_content="Score: 95.1%"`, `benchmark_variant="MMLU"`
- Claude-4 on SWE-bench: `raw_content="Achieved 89.7%"`, `benchmark_variant="SWE-bench Verified"`

Add a second organization's events:
- Anthropic source + page
- Claude-4-sonnet release event
- Claude-4-sonnet benchmark events

Add cross-references:
- `confirms` link between GPT-5 events from different sources

Add claims at multiple confidence tiers:
- `official_self_report`, `benchmark_owner_report`, `high_secondary`

### 9.2 Test Counts (estimated per service)

| Test File | Tests | Coverage |
|---|---|---|
| `test_spotlight.py` | 8 | empty DB, single model, multiple models, min_benchmarks filter, org filter, debut_strength ranking, xref count, insight flags |
| `test_evolution.py` | 10 | empty DB, single benchmark, all benchmarks, rate computation, frontier progression, saturation percentage, saturation None for Elo, gap_to_second, window filtering, no scores |
| `test_capability.py` | 8 | empty DB, single model, percentile computation, composite score, compare_capabilities multi-model, model not found, single benchmark, equal-score tie |
| `test_landscape.py` | 7 | empty DB, single org, multi-org ranking, new model detection, pricing events, cluster count, trend computation |
| `test_research_pipeline.py` | 7 | empty DB, velocity computation, topic trends rising/falling/stable, predictive signals, no papers, min_citations filter, paper-product enrichment |
| `test_verification.py` | 8 | empty DB, model verification, confirmed pct, conflicted pct, source count, confidence tier ordering, benchmark variance, system summary |
| `test_correlation.py` | 7 | empty DB, sufficient overlap, insufficient overlap (min_overlap), correlation computation, label assignment, cluster detection, single benchmark (no pairs) |
| `test_formatters.py` (extend) | 7 | one formatter test per new product type |

**Estimated total new tests: ~62**

### 9.3 Verification Commands

```bash
# All tests pass
pytest

# Lint clean
ruff check ai_benchmark/ tests/
ruff format --check ai_benchmark/ tests/

# CLI smoke tests
ai-benchmark analyze spotlight --days 30 --format markdown
ai-benchmark analyze evolution --days 180 --format markdown
ai-benchmark analyze capability gpt-5
ai-benchmark analyze landscape --days 30
ai-benchmark analyze research-pipeline --days 90
ai-benchmark analyze verification
ai-benchmark analyze correlations
ai-benchmark analyze digest --days 7 --format markdown  # includes new fields
```

## 10. Files to Create

| File | Purpose | Estimated Lines |
|---|---|---|
| `ai_benchmark/analysis/services/spotlight.py` | Product 1: New Model Spotlight | ~80 |
| `ai_benchmark/analysis/services/evolution.py` | Product 2: Benchmark Evolution | ~120 |
| `ai_benchmark/analysis/services/capability.py` | Product 3: Cross-Benchmark Capability | ~90 |
| `ai_benchmark/analysis/services/landscape.py` | Product 4: Competitive Landscape | ~120 |
| `ai_benchmark/analysis/services/research_pipeline.py` | Product 5: Research Pipeline | ~100 |
| `ai_benchmark/analysis/services/verification.py` | Product 6: Claim Verification | ~120 |
| `ai_benchmark/analysis/services/correlation.py` | Product 7: Benchmark Correlation | ~90 |
| `tests/test_analysis/test_spotlight.py` | Spotlight tests | ~100 |
| `tests/test_analysis/test_evolution.py` | Evolution tests | ~130 |
| `tests/test_analysis/test_capability.py` | Capability tests | ~110 |
| `tests/test_analysis/test_landscape.py` | Landscape tests | ~100 |
| `tests/test_analysis/test_research_pipeline.py` | Research Pipeline tests | ~100 |
| `tests/test_analysis/test_verification.py` | Verification tests | ~120 |
| `tests/test_analysis/test_correlation.py` | Correlation tests | ~100 |

## 11. Files to Modify

| File | Change | Estimated Delta |
|---|---|---|
| `ai_benchmark/analysis/types.py` | Add 16 new dataclasses, extend DigestReport | +130 lines |
| `ai_benchmark/analysis/services/digest.py` | Import and call spotlight + evolution services | +15 lines |
| `ai_benchmark/analysis/formatters/markdown.py` | Add 7 new renderers, extend digest renderer | +180 lines |
| `ai_benchmark/analysis/formatters/csv_export.py` | Add 4 new CSV exporters | +80 lines |
| `ai_benchmark/analysis/cli.py` | Add 7 new subcommands | +200 lines |
| `ai_benchmark/analysis/api.py` | Add 9 new endpoints | +120 lines |
| `tests/test_analysis/conftest.py` | Extend fixtures with multi-org data, xrefs, varied claims | +60 lines |
| `tests/test_analysis/test_formatters.py` | Add 7 formatter tests | +70 lines |
| `CLAUDE.md` | Update Analysis Architecture section, test count | +20 lines |

**Estimated total new code: ~2,235 lines**
**Estimated total modified code: +875 lines**
