# Physical Design Requirements: Analysis Pipeline

**Source document:** `docs/analysis_pipeline_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-29 06:00 PM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| Base ORM class | `ai_benchmark/models/base.py` | Inherit `Base` for new models |
| Engine/session factory | `ai_benchmark/models/base.py` | `create_engine()`, `create_session_factory()` |
| EventRecord model | `ai_benchmark/models/events.py` | Primary data source — query by model_slug, event_type, organization, observed_at |
| ClaimRecord model | `ai_benchmark/models/events.py` | Confidence tiers, confirmation status |
| CrossReference model | `ai_benchmark/models/events.py` | Related event links |
| EnrichedPaper model | `ai_benchmark/models/research.py` | Citation counts, relevance tags, venues |
| CandidatePaper model | `ai_benchmark/models/research.py` | Paper discovery pipeline status |
| PipelineSettings | `ai_benchmark/config/settings.py` | Database URL, env prefix pattern |
| CLI entry point | `ai_benchmark/cli.py` | Register analyze group at line 276 (after eval group) |
| Eval CLI pattern | `ai_benchmark/eval/cli/commands.py` | Click group, asyncio.run wrapper, engine helper |
| Eval service pattern | `ai_benchmark/eval/services/comparison_service.py` | Async functions, AsyncSession first param, dict returns |
| Eval API pattern | `ai_benchmark/eval/api/app.py` | `include_router()`, `get_session()` dependency, model imports in lifespan |
| Eval route pattern | `ai_benchmark/eval/api/routes/evaluations.py` | `APIRouter()`, `Depends(get_session)`, `HTTPException` |
| Reporting queries | `ai_benchmark/reporting/query.py` | `get_events()`, `count_events_by_org()` — reuse or supersede |
| Reporting export | `ai_benchmark/reporting/export.py` | Pattern for JSON/CSV serialization |
| Alembic migrations | `alembic/versions/` | Migration 008 follows pattern from 006 |
| Number extraction | `ai_benchmark/processing/cross_reference.py:69` | `_extract_numbers()` — reuse for benchmark score extraction |
| Normalizer | `ai_benchmark/processing/normalizer.py` | `extract_model_slug()`, `classify_event_type()` patterns |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| (none) | No new dependencies required | — |

All implementation uses stdlib (`dataclasses`, `re`, `json`, `csv`, `io`, `collections`) plus existing project deps (SQLAlchemy, Click, FastAPI, structlog).

## 2. Package Layout

```
ai_benchmark/analysis/
├── __init__.py                          # Package marker
├── models.py                            # AnalysisSnapshot + AnalysisInsight ORM tables
├── types.py                             # Result dataclasses (no DB dependency)
├── services/
│   ├── __init__.py                      # Package marker
│   ├── model_lifecycle.py               # Product 1: model profiles and timelines
│   ├── benchmark_trends.py              # Product 2: leaderboards and score trends
│   ├── competitive_intel.py             # Product 3: cross-vendor activity
│   ├── research_pulse.py                # Product 4: research trends
│   ├── anomaly_detector.py              # Product 5: insight detection
│   └── digest.py                        # Product 6: periodic digest orchestrator
├── formatters/
│   ├── __init__.py                      # Package marker
│   ├── markdown.py                      # Markdown rendering
│   ├── json_export.py                   # JSON serialization
│   └── csv_export.py                    # CSV serialization
├── cli.py                               # Click group + subcommands
└── api.py                               # FastAPI router

alembic/versions/
└── 008_analysis_pipeline.py             # New tables + indexes

tests/test_analysis/
├── __init__.py
├── conftest.py                          # Shared fixtures (async session, sample data)
├── test_models.py                       # ORM model tests
├── test_types.py                        # Dataclass tests
├── test_model_lifecycle.py              # Service tests
├── test_benchmark_trends.py             # Service tests
├── test_competitive_intel.py            # Service tests
├── test_research_pulse.py               # Service tests
├── test_anomaly_detector.py             # Service tests
├── test_digest.py                       # Integration test
├── test_formatters.py                   # Formatter tests
├── test_cli.py                          # CLI tests
└── test_api.py                          # API endpoint tests
```

Files to modify:

| File | Change |
|---|---|
| `ai_benchmark/cli.py` | Add `from .analysis.cli import analyze_group` and `cli.add_command(analyze_group)` after line 276 |
| `ai_benchmark/eval/api/app.py` | Add `from ...analysis.api import router as analysis_router` and `app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])` after line 213 |
| `ai_benchmark/eval/api/app.py` | Add `from ...analysis import models as analysis_models  # noqa: F401` in lifespan at line 122 |

## 3. Data Model

### 3.1 `analysis_snapshots` Table

Persists analysis results for caching and historical comparison.

```python
class AnalysisSnapshot(Base):
    __tablename__ = "analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(50))
    scope_key: Mapped[str] = mapped_column(String(200))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[str] = mapped_column(Text)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
```

**analysis_type values:** `model_lifecycle`, `benchmark_trends`, `competitive_intel`, `research_pulse`, `anomalies`, `digest`

**scope_key examples:** model slug (`gpt-4o`), benchmark name (`SWE-bench Verified`), org name (`OpenAI`), digest period (`weekly-2026-W13`), or `global` for cross-scope analyses.

### 3.2 `analysis_insights` Table

Individual flagged findings for querying and digest inclusion.

```python
class AnalysisInsight(Base):
    __tablename__ = "analysis_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    insight_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    related_event_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_model_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    related_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_snapshots.id"), nullable=True
    )
```

**insight_type values:** `new_model`, `price_drop`, `benchmark_record`, `competitive_cluster`, `new_org`, `rapid_iteration`, `conflict_detected`, `paper_to_product`

**severity values:** `info`, `notable`, `critical`

**related_event_ids format:** Comma-separated integers, e.g. `"42,57,103"`

### 3.3 Index Additions on Existing Tables

These indexes support the analysis services' most common query patterns.

| Table | Index Name | Column(s) |
|---|---|---|
| `event_records` | `ix_event_records_model_slug` | `model_slug` |
| `event_records` | `ix_event_records_organization` | `organization` |
| `event_records` | `ix_event_records_event_type` | `event_type` |
| `event_records` | `ix_event_records_observed_at` | `observed_at` |
| `event_records` | `ix_event_records_benchmark_variant` | `benchmark_variant` |
| `claim_records` | `ix_claim_records_event_id` | `event_id` |
| `enriched_papers` | `ix_enriched_papers_citation_count` | `citation_count` |

## 4. Result Dataclasses

All in `ai_benchmark/analysis/types.py`. These are pure data containers with no DB dependency.

```python
@dataclass
class ModelSummary:
    model_slug: str
    organization: str
    first_seen: str | None          # YYYY-MM-DD
    latest_activity: str | None     # YYYY-MM-DD
    event_count: int
    status: str                     # active | deprecated | announced

@dataclass
class TimelineEntry:
    date: str                       # YYYY-MM-DD or ISO datetime
    event_type: str
    title: str
    confidence_tier: str
    confirmation_status: str
    event_id: int

@dataclass
class ModelProfile:
    model_slug: str
    organization: str
    first_seen: str | None
    latest_activity: str | None
    status: str
    milestones: list[TimelineEntry]
    claim_summary: dict[str, int]   # {confirmed: N, unconfirmed: N, conflicted: N}
    benchmark_scores: list[BenchmarkDataPoint]
    related_models: list[str]

@dataclass
class ModelComparisonMatrix:
    model_slugs: list[str]
    profiles: dict[str, ModelProfile]

@dataclass
class BenchmarkDataPoint:
    model_slug: str
    score: float | None
    date: str
    source_name: str
    benchmark_variant: str

@dataclass
class BenchmarkSummary:
    benchmark_name: str
    entry_count: int
    latest_date: str | None
    top_model: str | None
    top_score: float | None

@dataclass
class Leaderboard:
    benchmark_name: str
    as_of: str
    entries: list[BenchmarkDataPoint]

@dataclass
class OrgActivity:
    organization: str
    event_counts: dict[str, int]    # event_type -> count
    active_models: list[str]
    total_events: int

@dataclass
class CompetitiveCluster:
    start_date: str
    end_date: str
    event_type: str
    organizations: list[str]
    event_count: int
    event_ids: list[int]

@dataclass
class ActivityTimeline:
    window_start: str
    window_end: str
    org_activities: list[OrgActivity]
    clusters: list[CompetitiveCluster]

@dataclass
class PaperCitationEntry:
    title: str
    arxiv_id: str | None
    citation_count: int
    venue: str | None
    enriched_at: str

@dataclass
class PaperProductLink:
    paper_title: str
    paper_arxiv_id: str | None
    model_slug: str
    organization: str
    lag_days: int

@dataclass
class ResearchTrends:
    window_days: int
    total_papers: int
    promoted_count: int
    rejected_count: int
    pending_count: int
    citation_leaders: list[PaperCitationEntry]
    topic_counts: dict[str, int]    # tag -> frequency
    paper_product_links: list[PaperProductLink]

@dataclass
class DigestReport:
    period_start: str
    period_end: str
    headline_insights: list[dict]
    model_updates: list[ModelSummary]
    benchmark_movements: list[BenchmarkDataPoint]
    competitive_overview: ActivityTimeline
    research_highlights: ResearchTrends
    stats: dict[str, int]           # {new_events, new_claims, new_papers, new_insights}
```

## 5. Service Interfaces

All services follow: `async def function(session: AsyncSession, ...) -> ReturnType`. Session is always the first parameter. TYPE_CHECKING import for AsyncSession.

### 5.1 Model Lifecycle Service — `services/model_lifecycle.py`

```python
async def list_tracked_models(
    session: AsyncSession,
    *,
    organization: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ModelSummary]:
    """All distinct model_slugs with event counts and date ranges."""

async def build_model_profile(
    session: AsyncSession,
    model_slug: str,
) -> ModelProfile | None:
    """Complete lifecycle for one model. Returns None if slug not found."""

async def get_model_timeline(
    session: AsyncSession,
    model_slug: str,
) -> list[TimelineEntry]:
    """Ordered event timeline for a model."""

async def compare_models(
    session: AsyncSession,
    model_slugs: list[str],
) -> ModelComparisonMatrix:
    """Side-by-side comparison of multiple models."""
```

**Implementation notes:**
- `list_tracked_models`: `SELECT model_slug, organization, MIN(observed_at), MAX(observed_at), COUNT(*) FROM event_records WHERE model_slug IS NOT NULL GROUP BY model_slug, organization`
- Status inference: `deprecated` if any event has `event_type='deprecation'`, `announced` if only 1 event of type `announcement`, else `active`
- `build_model_profile`: Single query for events + subquery for claims via `event_id IN (...)`. Extract benchmark scores from events where `benchmark_variant IS NOT NULL` using score extraction helper.

### 5.2 Benchmark Trends Service — `services/benchmark_trends.py`

```python
def extract_benchmark_score(raw_content: str, benchmark_name: str | None = None) -> float | None:
    """Best-effort score extraction from unstructured text.
    Handles: '92.3%', 'Elo: 1287', '0.623 on X', 'scored 85.1'."""

async def list_benchmarks(session: AsyncSession) -> list[BenchmarkSummary]:
    """All tracked benchmarks with entry counts."""

async def get_benchmark_leaderboard(
    session: AsyncSession,
    benchmark_name: str,
    *,
    as_of: datetime | None = None,
) -> Leaderboard:
    """Point-in-time leaderboard. Default: latest data."""

async def get_benchmark_timeline(
    session: AsyncSession,
    benchmark_name: str,
    *,
    model_slug: str | None = None,
) -> list[BenchmarkDataPoint]:
    """Time series of scores, optionally filtered by model."""
```

**Implementation notes:**
- Query `EventRecord WHERE benchmark_variant LIKE '%{benchmark_name}%'`
- `extract_benchmark_score`: Priority order — (1) percentage `(\d+\.?\d*)\s*%`, (2) Elo-like `(?:elo|rating|score)[:\s]+(\d+\.?\d*)`, (3) decimal `(\d+\.\d+)` > 0 and < 1, (4) bare integer `(\d{2,4})` not in model slug. Returns `None` on failure.
- Leaderboard: Group by model_slug, take latest entry per model, sort by score DESC.

### 5.3 Competitive Intelligence Service — `services/competitive_intel.py`

```python
async def get_activity_timeline(
    session: AsyncSession,
    *,
    window_days: int = 30,
    organizations: list[str] | None = None,
) -> ActivityTimeline:
    """Cross-org activity for a time window."""

async def detect_competitive_clusters(
    session: AsyncSession,
    *,
    window_days: int = 7,
    min_orgs: int = 2,
) -> list[CompetitiveCluster]:
    """Find time windows where 2+ orgs had similar event types."""

async def org_activity_summary(
    session: AsyncSession,
    organization: str,
    *,
    window_days: int = 90,
) -> OrgActivity:
    """Per-org activity summary."""
```

**Implementation notes:**
- Cluster detection: Load all events in window, group by (event_type, week_bucket). A cluster exists when a (event_type, week) group contains 2+ distinct organizations.
- Week bucket: `event.observed_at.isocalendar()[:2]` → `(year, week)`

### 5.4 Research Pulse Service — `services/research_pulse.py`

```python
async def get_research_trends(
    session: AsyncSession,
    *,
    window_days: int = 90,
) -> ResearchTrends:
    """Trending topics, citation leaders, paper-to-product lag."""

async def get_citation_leaders(
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[PaperCitationEntry]:
    """Top papers by citation count."""

async def detect_paper_to_product(
    session: AsyncSession,
    *,
    max_lag_days: int = 180,
) -> list[PaperProductLink]:
    """Match enriched papers to model_release events by org + time."""
```

**Implementation notes:**
- Topic counts: Parse `EnrichedPaper.relevance_tags` (comma-separated string), count frequencies.
- Paper-to-product: For each EnrichedPaper, check if `authors` field contains any org name from tracked organizations. If match found, look for `model_release` EventRecords from that org within `max_lag_days` of `enriched_at`.
- Citation leaders: `SELECT * FROM enriched_papers ORDER BY citation_count DESC LIMIT N`

### 5.5 Anomaly Detector Service — `services/anomaly_detector.py`

```python
async def detect_anomalies(
    session: AsyncSession,
    *,
    window_days: int = 7,
) -> list[AnalysisInsight]:
    """Run all rules, persist new insights, return them."""

async def get_recent_insights(
    session: AsyncSession,
    *,
    limit: int = 20,
    severity: str | None = None,
    insight_type: str | None = None,
) -> list[AnalysisInsight]:
    """Query persisted insights with filters."""
```

**Anomaly rules (private functions):**

| Rule | Insight Type | Severity | Detection Logic |
|---|---|---|---|
| `_detect_new_orgs` | `new_org` | `notable` | Org in recent events not in older events |
| `_detect_rapid_iteration` | `rapid_iteration` | `info` | 3+ events for same model_slug in 7 days |
| `_detect_benchmark_records` | `benchmark_record` | `notable` | Score exceeds previous max for benchmark_variant |
| `_detect_conflicts` | `conflict_detected` | `critical` | Claims with `confirmation_status='conflicted'` |
| `_detect_price_drops` | `price_drop` | `notable` | `pricing_change` events with decrease indicators in raw_content |
| `_detect_new_model_families` | `new_model` | `info` | First event for a model family prefix (e.g., first `grok-3-*` when only `grok-2-*` existed) |

**Idempotency:** Each rule checks `SELECT id FROM analysis_insights WHERE insight_type = ? AND related_event_ids = ?` before creating. Events already covered by an existing insight are skipped.

### 5.6 Digest Service — `services/digest.py`

```python
async def generate_digest(
    session: AsyncSession,
    *,
    window_days: int = 7,
    persist: bool = True,
) -> DigestReport:
    """Orchestrate all services into a single digest."""
```

**Implementation notes:**
- Calls `list_tracked_models`, `list_benchmarks`, `get_activity_timeline`, `get_research_trends`, `detect_anomalies` with the same window.
- Filters model_updates to only models with new activity in the window.
- Filters benchmark_movements to entries with dates in the window.
- If `persist=True`, saves `AnalysisSnapshot(analysis_type='digest', scope_key=f'weekly-{iso_week}', result_json=json.dumps(asdict(report)))`.

## 6. Formatter Interfaces

### 6.1 Markdown — `formatters/markdown.py`

```python
def model_profile_to_markdown(profile: ModelProfile) -> str:
def model_list_to_markdown(models: list[ModelSummary]) -> str:
def leaderboard_to_markdown(leaderboard: Leaderboard) -> str:
def activity_timeline_to_markdown(timeline: ActivityTimeline) -> str:
def research_trends_to_markdown(trends: ResearchTrends) -> str:
def insights_to_markdown(insights: list[AnalysisInsight]) -> str:
def digest_to_markdown(digest: DigestReport) -> str:
```

### 6.2 JSON — `formatters/json_export.py`

```python
def to_json(data: Any, indent: int = 2) -> str:
    """Serialize dataclass or dict to JSON. Uses dataclasses.asdict for dataclasses."""
```

### 6.3 CSV — `formatters/csv_export.py`

```python
def models_to_csv(models: list[ModelSummary]) -> str:
def leaderboard_to_csv(leaderboard: Leaderboard) -> str:
def insights_to_csv(insights: list[AnalysisInsight]) -> str:
```

## 7. CLI Commands

Click group `analyze` with 9 subcommands, registered in `cli.py` after eval group.

| Command | Options | Description |
|---|---|---|
| `analyze models` | `--org`, `--format` | List tracked models |
| `analyze model <slug>` | `--format` | Model lifecycle profile |
| `analyze benchmarks` | — | List tracked benchmarks |
| `analyze benchmark <name>` | `--model`, `--format` | Benchmark leaderboard/timeline |
| `analyze competitive` | `--days`, `--org` (multi), `--format` | Cross-vendor activity |
| `analyze research` | `--days`, `--format` | Research trends |
| `analyze anomalies` | `--days`, `--severity` | Detected insights |
| `analyze digest` | `--days`, `--format`, `--output` | Full periodic digest |
| `analyze run-all` | `--days` | Run all services, persist results |

**CLI engine helper** (mirrors eval pattern):

```python
def _get_analysis_engine(settings):
    engine = create_engine(settings.database_url)
    from ..models import discovery, events, research, sources  # noqa: F401
    from . import models as analysis_models  # noqa: F401
    return engine
```

## 8. API Endpoints

FastAPI router in `analysis/api.py`, mounted at `/api/analysis/` on the eval app.

| Method | Path | Service Call | Response |
|---|---|---|---|
| GET | `/models` | `list_tracked_models(org=)` | `list[ModelSummary]` as JSON |
| GET | `/models/{slug}` | `build_model_profile(slug)` | `ModelProfile` as JSON |
| GET | `/models/{slug}/timeline` | `get_model_timeline(slug)` | `list[TimelineEntry]` as JSON |
| GET | `/benchmarks` | `list_benchmarks()` | `list[BenchmarkSummary]` as JSON |
| GET | `/benchmarks/{name}` | `get_benchmark_leaderboard(name)` | `Leaderboard` as JSON |
| GET | `/benchmarks/{name}/timeline` | `get_benchmark_timeline(name)` | `list[BenchmarkDataPoint]` as JSON |
| GET | `/competitive` | `get_activity_timeline(days=)` | `ActivityTimeline` as JSON |
| GET | `/research` | `get_research_trends(days=)` | `ResearchTrends` as JSON |
| GET | `/insights` | `get_recent_insights(severity=, limit=)` | `list[AnalysisInsight]` as JSON |
| GET | `/digest` | `generate_digest(days=, persist=False)` | `DigestReport` as JSON |
| POST | `/digest` | `generate_digest(days=, persist=True)` | `DigestReport` as JSON |

**Session pattern:** `session: AsyncSession = Depends(get_session)` using the eval app's session factory.

**Error pattern:** `raise HTTPException(404, "Model not found")` when entity missing.

**Serialization:** Convert dataclasses via `dataclasses.asdict()`, ORM models via helper functions. All responses are plain dicts — no Pydantic response models needed (matches eval comparison pattern).

## 9. Migration

`alembic/versions/008_analysis_pipeline.py` — revision `"008"`, down_revision `"007"`.

Creates 2 tables and 7 indexes. Follows exact pattern of `006_discovery_automation.py`.

## 10. Verification Criteria

| Criterion | Command | Expected |
|---|---|---|
| Existing tests pass | `pytest` | 666+ tests pass, 0 failures |
| Lint clean | `ruff check ai_benchmark/ tests/` | Exit 0 |
| Format clean | `ruff format --check ai_benchmark/ tests/` | Exit 0 |
| Migration applies | `alembic upgrade head` | Creates tables + indexes |
| DB init works | `ai-benchmark init-db` | Tables created |
| Model listing works | `ai-benchmark analyze models` | Shows tracked models |
| Model profile works | `ai-benchmark analyze model <slug>` | Shows lifecycle |
| Benchmark listing works | `ai-benchmark analyze benchmarks` | Shows benchmarks |
| Digest works | `ai-benchmark analyze digest --days 7` | Produces report |
| API endpoints respond | `curl localhost:8100/api/analysis/models` | JSON response |
| New tests pass | `pytest tests/test_analysis/` | All pass |
