# AI Benchmark Intelligence Pipeline

Monitors AI model releases, benchmark results, pricing changes, and research papers across 22 sources. Produces a structured local knowledge base of verified AI industry events with multi-layer deduplication, a 5-chain verification hierarchy, and cross-referencing.

Requires Python 3.12+.

## Setup

```bash
pip install -e ".[dev]"
ai-benchmark init-db
ai-benchmark check-config
```

For research paper enrichment (Semantic Scholar, PDF parsing):

```bash
pip install -e ".[dev,research]"
```

## CLI

```bash
ai-benchmark init-db                    # Create/migrate database schema
ai-benchmark check-config               # Validate source catalog and settings
ai-benchmark collect                     # Run collection for all sources
ai-benchmark collect --source OpenAI     # Collect from a single source
ai-benchmark run                         # Start daemon with scheduled collection
ai-benchmark status                      # Show per-source event counts
ai-benchmark query                       # Search events (text output)
ai-benchmark query --org OpenAI --format json  # Filter + JSON output
ai-benchmark query --model gpt-5         # Search by model slug
ai-benchmark export --format csv --output events.csv  # Export to file
```

## Architecture

```
ai_benchmark/
  config/           Settings (Pydantic + env vars), TOML source catalog,
                    TOML schedule definitions
  models/           SQLAlchemy 2.0 async ORM (Source, Page, Snapshot, EventRecord,
                    ClaimRecord, CrossReference, CandidatePaper, EnrichedPaper,
                    FollowUpTask)
  collection/       HTTP fetcher (httpx, retry/backoff), HTML differ, snapshot manager,
                    base API client
  sources/          22 registered collectors (HTML + RSS + API collection methods)
    openai.py, anthropic.py, google.py, xai.py, mistral.py, cohere.py, meta.py
    base.py         SourceCollector ABC with shared Google News RSS parser
    benchmarks/     Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE,
                    Terminal-Bench (HTML + RSS fallback)
    research/       arXiv (HTML), Semantic Scholar (API), HF Papers (HTML)
    news/           Reuters (Google News RSS), TechCrunch (WordPress RSS + HTML)
    community/      HF Forums (Discourse JSON API + HTML), GitHub discovery (GitHub API),
                    HF Leaderboard Docs (HTML)
  processing/       Normalizer, deduplicator (composite key + model slug + fuzzy),
                    verification hierarchy (5 chains), cross-reference builder
                    (3 strategies: model-slug, org+event-type, arXiv ID → cites),
                    triage pipeline, quality filter, discovery queue (real fetch
                    execution), path prober, full processing pipeline
  scheduling/       APScheduler async scheduler, cron cadence config, health tracking
                    with circuit breaker
  reporting/        Query functions (events, claims, cross-refs, research counts),
                    JSON/CSV export
  eval/             Model evaluation pipeline (see below)
```

## Source Coverage

All 22 sources from the requirements are implemented:

| Category | Sources | Trust |
|---|---|---|
| Official vendors (7) | OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta | 4.5–5.0 |
| Benchmarks (7) | Artificial Analysis, LMArena (incl. image/vision), LiveBench, SWE-bench (incl. Pro), GAIA, HLE (multi-slice), Terminal-Bench | 4.0–4.5 |
| Research feeds (3) | arXiv, Semantic Scholar, HF Papers | 4.0 |
| News (2) | Reuters (high secondary), TechCrunch (medium discovery) | 3.5–4.0 |
| Community (3) | HF Forums, GitHub discovery, HF Leaderboard Docs | 3.0 |

## Verification Hierarchy

Events are verified through 5 chains:

1. **Model releases**: Confirmed when 2+ official surfaces agree
2. **Benchmark claims**: Benchmark owner report required; variant (e.g., SWE-bench Pro vs Verified) and evaluation conditions always recorded
3. **Pricing changes**: Only confirmed from pricing page changes (both docs and main pricing pages monitored)
4. **Announcements**: Newsroom + at least one other source
5. **Research claims**: Primary paper required

Claims from different sources are stored as separate records — never merged.

Confidence tiers (5 standard values): `official_self_report`, `benchmark_owner_report`, `high_secondary`, `medium_discovery`, `low_discovery`. All tiers are enforced uniformly across the verification and normalization modules.

## How the Extract Pipeline Works

The extract pipeline collects, processes, and verifies AI industry events from 22 sources across 87 monitored pages. It runs either as a one-shot command (`ai-benchmark collect`) or as a long-running daemon with cron-scheduled jobs (`ai-benchmark run`).

### Pipeline Overview

```
                          ┌─────────────────────────────────┐
                          │  CLI: collect / run (daemon)    │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │  Scheduler                      │
                          │  Loads sources.toml + schedules  │
                          │  Iterates each organization     │
                          └──────────────┬──────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
   ┌────────▼─────────┐     ┌───────────▼──────────┐     ┌──────────▼──────────┐
   │ HTML Fetch + Diff │     │ Google News RSS      │     │ API Call            │
   │ (primary method)  │     │ (Cloudflare fallback)│     │ (GitHub, S2, HF)    │
   └────────┬──────────┘     └───────────┬──────────┘     └──────────┬──────────┘
            │                            │                            │
            └────────────────────────────┼────────────────────────────┘
                                         │
                               ┌─────────▼─────────┐
                               │  Quality Filter    │
                               │  (stale, trivial,  │
                               │   garbage removal) │
                               └─────────┬─────────┘
                                         │
                               ┌─────────▼─────────┐
                               │  RawItem list      │
                               └─────────┬─────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │  Processing Pipeline            │
                          │  normalize → discovery check →  │
                          │  dedup → create event/claim →   │
                          │  verify → cross-reference       │
                          └──────────────┬──────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                                         │
           ┌────────▼─────────┐                    ┌─────────▼──────────┐
           │  EventRecord +   │                    │  Research Triage   │
           │  ClaimRecord     │                    │  (candidate_paper  │
           │  (standard items)│                    │   items only)      │
           └──────────────────┘                    └────────────────────┘
```

### Stage 1: Collection

The scheduler loads the source catalog (`config/sources.toml`) and iterates each organization. For each source, it resolves the appropriate collector from the registry (`sources/registry.py`) and processes every page defined for that source.

**Three collection methods:**

1. **HTML fetch + diff** (primary) — The fetcher (`collection/fetcher.py`) downloads the page with httpx, using retry with exponential backoff, rate-limit handling (429 → Retry-After), and concurrency control via semaphore. The snapshot manager (`collection/snapshot.py`) compares the new HTML against the prior snapshot using SHA-256 hash (fast path) and `difflib.SequenceMatcher` (detailed diff). If the page hasn't changed, it's skipped. If it has changed, the collector's `extract_items()` method parses the HTML into `RawItem` objects.

2. **Google News RSS** (fallback for Cloudflare-blocked or JS-rendered sites) — Pages with `rss` in their page type are parsed by the shared `_extract_google_news_rss()` helper in the base collector. This extracts title, link, publication date, and description from standard RSS XML. Used by xAI, Mistral, Cohere, Meta, and all benchmark sources as a fallback.

3. **API calls** (GitHub, Semantic Scholar, HF Forums) — Collectors that use APIs override `collect_page()` to bypass HTML fetching entirely and call their API methods directly. GitHub discovery calls the GitHub REST API for org repos and recent releases. Semantic Scholar calls its search API with keyword queries. HF Forums calls the Discourse JSON API (`/latest.json`).

**Fetcher details:**
- User agent mimics Chrome to avoid bot detection
- HTTP/2 support enabled
- Default 30-second timeout, 5 max concurrent requests, 3 retry attempts
- 403 responses treated as terminal (no retry); 429 responses sleep and retry
- Optional HTTP proxy support

### Stage 2: Quality Filter

Before items enter the processing pipeline, the quality filter (`processing/quality_filter.py`) removes low-value pages:

- **Trivial changes on stable pages** — If the page has been polled 5+ times and the change ratio is below 1%, the page is skipped.
- **Garbage extraction** — If all extracted titles are shorter than 5 characters, the page is skipped.
- **Stale content** — If no extracted item has a date within the last 90 days, the page is skipped. This check is disabled on first-ever fetch (cold start) and for inherently dateless page types (leaderboards, pricing, model catalogs).

### Stage 3: Processing Pipeline

Each `RawItem` flows through `processing/pipeline.py` in this order:

1. **Route research items** — Items with `item_type="candidate_paper"` (from arXiv, Semantic Scholar, HF Papers) are diverted to the research triage pipeline and do not create events. They appear as "Papers" in status output, not "Events".

2. **Normalize** (`processing/normalizer.py`):
   - `normalize_title()` — Lowercase, strip, collapse whitespace
   - `extract_model_slug()` — Regex extraction for known model families (GPT, Claude, Gemini, Grok, Llama, Mistral, Command, etc.), normalized to lowercase-hyphenated form (e.g., "gpt-4-turbo")
   - `extract_date()` — Tries ISO format first, then 24 common date patterns, returns YYYY-MM-DD
   - `classify_event_type()` — Keyword scoring against 6 event types: `model_release`, `pricing_change`, `api_update`, `deprecation`, `system_card`, `announcement` (default)

3. **Discovery check** (`processing/discovery_queue.py`) — If a model slug was extracted, the discovery queue checks whether it's new. New slugs trigger 4 follow-up tasks: pricing search, release notes search, system card search, and benchmark coverage search. These tasks are executed on the next collection run, fetching the org's relevant pages and filtering for items that mention the new model.

4. **Deduplicate** (`processing/deduplicator.py`) — Three-layer strategy:
   - **Exact composite key**: normalized title + org + source type + URL + date + model slug
   - **Model slug + org + date**: Same model from same vendor on same day
   - **Fuzzy title match**: `SequenceMatcher` ratio ≥ 0.85 within the same organization

   If a duplicate is found, a new claim is created on the existing event (enabling multi-source confirmation) and no new event is created.

5. **Create event + claim** — If unique, an `EventRecord` is created with normalized title, organization, event type, model slug, and published date. A `ClaimRecord` is attached with a confidence tier derived from the source's classification:
   - `primary` → `official_self_report`
   - `benchmark_owner` → `benchmark_owner_report`
   - `secondary` → `high_secondary`
   - `news_medium` → `medium_discovery`
   - `discovery-only` → `low_discovery`

   Source-specific overrides exist (e.g., Reuters always maps to `high_secondary`).

6. **Verify** (`processing/verification.py`) — The verification module evaluates confirmation status using ordered verification chains per event type:
   - **Model releases**: Confirmed when 2+ distinct source types agree, with at least 1 from the top 3 (launch page, developer docs, model catalog)
   - **Benchmark results**: Requires at least one `benchmark_owner_report` claim
   - **Pricing changes**: Requires a `pricing_page` source claim
   - **Announcements**: Requires newsroom + 1 other source
   - **Research claims**: Requires a `primary_paper` claim

   Numerical conflict detection compares extracted values across claims — disagreement > 10% sets status to `conflicted`.

7. **Cross-reference** (`processing/cross_reference.py`) — Three linking strategies:
   - **Model slug + time window**: Same model mentioned by different sources within 7 days → `confirms` or `supplements`
   - **Org + event type**: Same org, same event type within 3 days → `supplements`
   - **arXiv ID**: Shared arXiv ID in content → `cites`

   Relationship types: `confirms`, `supplements`, `conflicts_with`, `cites`.

### Research Triage (Separate Path)

Research items bypass event creation and enter a three-stage pipeline (`processing/triage.py`):

1. **Ingest** — `CandidatePaper` record created with title, arXiv ID, authors, categories, discovery source. Status: `pending`.
2. **Enrich** — Semantic Scholar API fetches metadata (abstract, venue, citation count, code URL). Relevance scored against keyword list (benchmark, evaluation, LLM, safety, etc.). Papers scoring ≥ 2 advance; others are rejected.
3. **Promote** — Enriched candidates become `EnrichedPaper` records in the authoritative store with full metadata.

Enrichment runs as a scheduled job, processing up to 50 pending candidates per cycle.

### Scheduling

**One-shot mode** (`ai-benchmark collect`): Runs collection for all sources (or one with `--source`) sequentially, then exits.

**Daemon mode** (`ai-benchmark run`): Starts an APScheduler `AsyncIOScheduler` with cron triggers loaded from `config/schedules.toml`. Each source has its own cron expression (vendors every 6h, Reuters every 3h, benchmarks daily, research twice daily). The scheduler includes:

- **Circuit breaker** (`scheduling/health.py`): After 5 consecutive failures for a source, the circuit opens and that source is skipped until manually reset. Success resets the counter.
- **Health tracking**: Per-source state with `last_success_at`, `last_failure_at`, `consecutive_failures`, and `last_error`.
- **Graceful shutdown**: Signal handlers (SIGINT/SIGTERM) stop the scheduler and close database connections.

### Monitoring Collection Runs

```bash
# Check per-source event and paper counts
ai-benchmark status

# Watch log output during a run
# PowerShell:
Get-Content C:\ai-benchmark\logs\collect_*.log -Wait -Tail 20
# Bash:
tail -f /c/ai-benchmark/logs/collect_*.log

# Check which sources completed vs. started
findstr "Collecting collection_complete" C:\ai-benchmark\logs\collect_*.log

# Check errors
findstr "ERROR WARNING fetch_failed" C:\ai-benchmark\logs\collect_*.log

# Query events after collection
ai-benchmark query --org OpenAI
ai-benchmark query --model gpt-4
ai-benchmark export --format csv --output events.csv
```

## Configuration

Settings are loaded via Pydantic with the `AI_BENCH_` env prefix. Also reads `.env` in the project root.

| Variable | Default | Purpose |
|---|---|---|
| `AI_BENCH_DATABASE_URL` | `sqlite+aiosqlite:///ai_benchmark.db` | Database connection string |
| `AI_BENCH_GITHUB_TOKEN` | — | GitHub API access (Meta repos, org discovery) |
| `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` | — | Semantic Scholar paper enrichment |
| `AI_BENCH_LOG_LEVEL` | `INFO` | Logging level |
| `AI_BENCH_LOG_FORMAT` | `json` | `json` or `console` output |
| `AI_BENCH_PROXY_URL` | — | HTTP proxy for fetcher |
| `AI_BENCH_REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `AI_BENCH_MAX_CONCURRENCY` | `5` | Max concurrent fetch requests |
| `AI_BENCH_RETRY_ATTEMPTS` | `3` | Retry count with exponential backoff |

Source catalog: `ai_benchmark/config/sources.toml` (22 sources, 86 pages)
Schedule config: `ai_benchmark/config/schedules.toml` (24 cron entries)

## Database Models

11 SQLAlchemy 2.0 async ORM models across 5 modules:

- **sources.py**: `Source`, `Page`, `Snapshot` — catalog, monitored pages, HTML content snapshots
- **events.py**: `EventRecord`, `ClaimRecord`, `CrossReference` — normalized events, per-source claims, inter-event links
- **research.py**: `CandidatePaper`, `EnrichedPaper` — research triage pipeline (discovered → enriched → promoted/rejected)
- **discovery.py**: `FollowUpTask` — model slug discovery queue follow-up tasks
- **analysis/models.py**: `AnalysisSnapshot`, `AnalysisInsight` — cached analysis results and flagged findings

## Analysis Pipeline

Transforms raw collected events into six structured intelligence products: model lifecycle profiles, benchmark leaderboards, competitive activity timelines, research pulse trends, automated anomaly detection, and periodic digests.

### Quick Start

```bash
ai-benchmark analyze models                        # List tracked AI models
ai-benchmark analyze model gpt-5                   # Model lifecycle profile
ai-benchmark analyze benchmarks                    # List tracked benchmarks
ai-benchmark analyze benchmark "SWE-bench"         # Benchmark leaderboard
ai-benchmark analyze competitive --days 30         # Cross-org activity
ai-benchmark analyze research --days 90            # Research trends
ai-benchmark analyze anomalies --days 7            # Detect anomalies
ai-benchmark analyze digest --days 7 --format md   # Full digest
ai-benchmark analyze run-all --days 7              # Run all services
```

All commands support `--format text|json|markdown|csv` where applicable.

### Analysis Architecture

```
ai_benchmark/analysis/
  models.py           AnalysisSnapshot + AnalysisInsight ORM tables
  types.py            31 result dataclasses (pure data, no DB dependency)
  services/           12 async service modules (model_lifecycle, benchmark_trends,
                      competitive_intel, research_pulse, anomaly_detector, digest,
                      spotlight, evolution, capability, landscape,
                      research_pipeline, verification, correlation)
  formatters/         Markdown, JSON, CSV output formatters
  cli.py              16 Click subcommands registered under 'analyze' group
  api.py              FastAPI router with 18 endpoints at /api/analysis/
```

### REST API

The analysis pipeline exposes 18 endpoints mounted at `/api/analysis/` on the eval server:

| Endpoint | Description |
|---|---|
| `GET /models` | List tracked models |
| `GET /models/{slug}` | Model lifecycle profile |
| `GET /models/{slug}/timeline` | Model event timeline |
| `GET /benchmarks` | List benchmarks |
| `GET /benchmarks/{name}` | Benchmark leaderboard |
| `GET /benchmarks/{name}/timeline` | Score time series |
| `GET /competitive` | Cross-org activity |
| `GET /research` | Research trends |
| `GET /insights` | Recent anomalies |
| `GET /digest` | Generate digest (no persist) |
| `POST /digest` | Generate and persist digest |
| `GET /spotlight` | New model spotlight |
| `GET /evolution` | Benchmark evolution trends |
| `GET /capability/{slug}` | Model capability profile |
| `GET /landscape` | Org landscape overview |
| `GET /research-pipeline` | Research pipeline analysis |
| `GET /verification` | Verification report |
| `GET /correlations` | Benchmark correlations |

## Model Evaluation Pipeline

A full evaluation subsystem for running, scoring, and comparing model outputs across machines, runtimes, and configurations.

### Quick Start

```bash
ai-benchmark eval serve                          # Start eval API + UI on port 8100
ai-benchmark eval run --evaluation X --target Y   # Run an evaluation
ai-benchmark eval status --recent 10              # Show recent runs
ai-benchmark eval compare --runs 1,2              # Compare two runs
ai-benchmark eval export --run 1 --format json    # Export results
ai-benchmark eval list --evaluations --targets    # List entities
```

### Eval Architecture

```
ai_benchmark/eval/
  models/         19 SQLAlchemy tables (datasets, dataset_versions, test_cases,
                  scorers, scorer_versions, evaluation_definitions,
                  evaluation_versions, machine_profiles, machine_snapshots,
                  target_configurations, runner_profiles, run_groups, runs,
                  run_item_results, run_aggregate_metrics, artifacts,
                  trace_references, annotations, eval_audit_log)
  services/       16 async service modules (dataset, scorer, eval, machine, target,
                  runner, run, comparison, report, compatibility, seed, validation,
                  matrix, artifact, audit, privacy)
  execution/      RunOrchestrator (with auto-artifact generation), ItemExecutor
                  (with trace capture), Dispatch engine, 13 model adapters
    adapters/     OpenAI, Anthropic, Ollama, LM Studio, llama.cpp, MLX, vLLM,
                  SGLang, TensorRT-LLM, OpenVINO GenAI, GenericHTTP,
                  OpenAI-compat, Local (legacy)
  scoring/        ScorerRunner + 7 built-in scorers (exact_match, fuzzy_match,
                  rubric, format_validator, latency_cost, safety, model_judge)
  api/            FastAPI with ~50 REST endpoints under /api/eval/,
                  API key auth middleware (X-API-Key / Bearer), /healthz
  ui/             Jinja2 templates: dashboard, entity pages, runner/run-group
                  pages, run detail/live/launch, comparison, search, reports,
                  create/clone/preview (28 templates)
  cli/            10 Click subcommands (run, run-matrix, status, list, compare,
                  export, rescore, serve, runners, machines)
  config.py       EvalSettings with AI_BENCH_EVAL_ env prefix
```

### Eval Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AI_BENCH_EVAL_API_HOST` | `127.0.0.1` | API bind host |
| `AI_BENCH_EVAL_API_PORT` | `8100` | API bind port |
| `AI_BENCH_EVAL_ARTIFACT_STORAGE_PATH` | `artifacts` | Artifact file storage |
| `AI_BENCH_EVAL_MAX_CONCURRENT_ITEMS` | `5` | Parallel item execution |
| `AI_BENCH_EVAL_DEFAULT_EXECUTION_MODE` | `sequential` | Default run mode |
| `AI_BENCH_EVAL_RUN_TIMEOUT_SECONDS` | `3600` | Per-run timeout |
| `AI_BENCH_EVAL_ITEM_TIMEOUT_SECONDS` | `120` | Per-item timeout |
| `AI_BENCH_EVAL_RETRY_FAILED_ITEMS` | `2` | Auto-retries per item |
| `AI_BENCH_EVAL_ARTIFACT_RETENTION_DAYS` | `90` | Max artifact age before cleanup |
| `AI_BENCH_EVAL_ARTIFACT_MAX_PER_RUN` | `20` | Max artifacts retained per run |

### Runner Comparison Platform

The eval pipeline is being extended into a full runner comparison platform that treats
the inference runner (Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM,
OpenVINO GenAI) as a first-class experimental variable. Results are
`model × machine × runner × configuration`, not just `model × machine`.

Target hardware: DGX Spark 128 GB, Apple Silicon M4 MBP 64 GB, Mac mini 24 GB,
RTX 4070 desktop, ASUS Vivobook S 15 (Intel NPU), GTX 1060 laptop, Raspberry Pi edge.

**Status**: All 14 phases complete — local-only privacy enforcement, audit trails
(AuditLogEntry model), retention controls (traces, raw outputs, artifacts), full
regression test suite across all UI workflows. Historical run filtering, traces tab,
comparison filters, report generation with runner/machine grouping, export to
JSON/CSV/HTML/Markdown. Sectioned navigation, runner/run-group pages, global search.
~50 REST endpoints, API key auth, 10 CLI subcommands, 13 model adapters, 19 tables,
16 services, 28 templates. Runner/machine registry with compatibility rules and
seed data for 7 target machines.

### Design Documents

- Naming conventions: `docs/naming_conventions.md`
- Eval automation examples: `docs/eval_automation_examples.md`
- Archived plans and design docs: `docs/archive/` (eval pipeline, runner comparison, gap remediation, etc.)

## Implementation Plans

### Active

- **Collection coordinator:** 4 phases — centralized coordinator replacing concurrent `collect_source()` calls to eliminate SQLite write contention (`docs/collection_coordinator_plan.md`)
- **Unified installer:** 6 phases — instance-aware installation, multi-instance support, in-place upgrades with rollback, unified CLI entry point (`docs/unified_installer_plan.md`)
- **Mistral/Cohere parser fixes:** 6 phases — RSC payload extraction for Mistral Next.js pages, Cohere RSS-only designation (`docs/mistral_cohere_parsers_plan.md`)
- **Data presentation layer:** 6 phases complete — spotlight, evolution, capability, landscape, research pipeline, verification, correlation (`docs/data_presentation_1_plan.md`)

### Archived (complete)

All completed plans in `docs/archive/`:

- **Source pipeline:** 7 phases complete
- **Eval pipeline:** 9 phases (E1–E9) complete
- **Gap remediation v1:** 6 phases (G1–G6), 66 tasks complete
- **Gap remediation v2:** 13 tasks complete
- **PEP8 compliance:** 7 phases complete
- **Runner comparison:** 14 phases complete
- **Code review remediation:** 4 phases complete (49 tasks)
- **Analysis pipeline:** 6 phases complete — model lifecycle, benchmark trends, competitive intel, research pulse, anomaly detection, digest + API

## Development

```bash
pip install -e ".[dev]"      # Install with dev + test dependencies
pytest                       # Run all tests (938 tests, 0 failures)
pytest tests/test_config.py  # Single test file
pytest -x -v                 # Verbose, stop on first failure
ruff check .                 # Lint
mypy ai_benchmark            # Type check (strict mode)
```

Key dev dependencies: pytest, pytest-asyncio, respx (httpx mocking), httpx (API tests), ruff, mypy.

## License

MIT
