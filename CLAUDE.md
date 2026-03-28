# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai_benchmark** is an AI model and benchmark intelligence pipeline. It monitors official AI company sources, benchmark leaderboards, research feeds, and news outlets to track model releases, pricing changes, benchmark results, and research papers. The system produces a structured local knowledge base of verified AI industry events.

## Build and Test

```bash
pip install -e ".[dev]"          # Install with dev dependencies
pip install -e ".[dev,research]" # Include research extras (S2, PDF)
pytest                           # Run all 297 tests
pytest tests/test_config.py      # Single file
pytest -x -v                     # Verbose, stop on first failure
ai-benchmark init-db             # Create database
ai-benchmark check-config        # Validate config
ai-benchmark collect --source OpenAI  # Test single source collection
ai-benchmark run                 # Start daemon mode
ai-benchmark status              # Show per-source event counts
ai-benchmark query --org OpenAI  # Search events
ai-benchmark export --format csv --output events.csv  # Export

# Eval pipeline commands
ai-benchmark eval serve                          # Start eval API + UI
ai-benchmark eval run --evaluation X --target Y   # Execute evaluation
ai-benchmark eval status --recent 10              # Show recent runs
ai-benchmark eval compare --runs 1,2              # Compare runs
ai-benchmark eval export --run 1 --format json    # Export results
ai-benchmark eval list --evaluations --targets    # List entities
ai-benchmark eval rescore --run 1 --scorer-config new.json  # Rescore
ai-benchmark eval run-matrix --evaluation X --targets 1,2,3  # Matrix run
```

## Core Domain Concepts

- **Source catalog**: 22 monitored sources across 5 categories — 21 polled collectors + Semantic Scholar enrichment client
- **Source classifications**: primary (official vendor pages), secondary (independent benchmarks, reputable news), discovery-only (community forums, arXiv, trending feeds)
- **Trust tiers**: sources rated 1-5; official vendor pages are 5, community sources as low as 3
- **Event records**: normalized change records with source, title, path, observed timestamp, and extracted model/version names
- **Claim records**: separate records per source for conflicting claims, with source_type, confidence tier, and cross-references — never merge conflicting claims prematurely
- **Confidence tiers**: official_self_report (primary), high_secondary (Reuters), medium_discovery (TechCrunch), low_discovery (forums, GitHub)

## Verification Hierarchy

This ordering is load-bearing for the entire pipeline:

1. **Model releases**: vendor launch surface > developer docs/model catalog > pricing > changelog/release notes > system card. Confirmed when at least two official surfaces align on model name and availability.
2. **Benchmark claims**: always check the benchmark owner first, not the vendor. Record variant (e.g., SWE-bench Verified vs Lite vs Pro) and evaluation conditions.
3. **Pricing changes**: only confirmed when the official pricing page changes. Store HTML snapshot + observation timestamp.
4. **Company announcements**: company newsroom/press first, then docs/product page, then Reuters, then other outlets.
5. **Research claims**: primary paper (arXiv/publisher) first, then Semantic Scholar metadata, then company blog narrative. Blog alone never confirms a technical claim.

## Processing Pipeline

Each collected item goes through: normalize → deduplicate → create event → create claim → update confirmation status → build cross-references. Duplicates from different sources still create claims on the existing event, enabling multi-source confirmation.

## Architecture

```
ai_benchmark/
  config/           Pydantic settings (env vars), TOML source catalog + schedule definitions
  models/           SQLAlchemy 2.0 async ORM — 8 models across 3 modules
  collection/       HTTP fetcher (httpx, retry/backoff), HTML differ, snapshot manager, API client
  sources/          21 registered source collectors + Semantic Scholar enrichment client
    benchmarks/     7 benchmark collectors (Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE, Terminal-Bench)
    research/       arXiv, Semantic Scholar, HF Papers
    news/           Reuters, TechCrunch
    community/      HF Forums, GitHub discovery, HF Leaderboard Docs
  processing/       Normalizer, deduplicator, verification, cross-reference builder, triage, pipeline orchestrator
  scheduling/       APScheduler async scheduler, cron cadence config, health tracker with circuit breaker
  reporting/        Query functions (events, claims, cross-refs), JSON/CSV export
  eval/             Model evaluation pipeline (see Eval Architecture below)
```

## Eval Architecture

```
ai_benchmark/eval/
  config.py         EvalSettings with AI_BENCH_EVAL_ env prefix
  models/           15 SQLAlchemy tables: datasets, dataset_versions, test_cases, scorers,
                    scorer_versions, evaluation_definitions, evaluation_versions, machine_profiles,
                    machine_snapshots, target_configurations, run_groups, runs, run_item_results,
                    run_aggregate_metrics, artifacts
  services/         8 async service modules: dataset, scorer, eval, machine, target, run,
                    comparison, report — all accept AsyncSession, return model instances
  execution/        RunOrchestrator (3-stage: create → execute → score/finalize),
                    ItemExecutor (prompt templating, retry), 4 model adapters
    adapters/       OpenAIAdapter, AnthropicAdapter, LocalAdapter, GenericHTTPAdapter
  scoring/          ScorerRunner (weighted pass logic, aggregate metrics), BaseScorer ABC
    builtin/        7 scorers: exact_match, fuzzy_match, rubric, format_validator,
                    latency_cost, safety, model_judge
  api/              FastAPI app factory, ~45 endpoints under /api/eval/
    routes/         evaluations, datasets, scorers, targets, machines, runs, comparisons, reports
    schemas/        Pydantic request/response models for all entities
  ui/               Jinja2 server-rendered UI with sidebar navigation
    templates/      14 HTML templates: dashboard, entity list/detail, run detail/live,
                    comparison view, reports dashboard with Chart.js
    static/         CSS (tables, cards, badges, progress bars) + JS (sorting, tabs, auto-refresh)
  cli/              9 Click subcommands: run, run-matrix, status, list, compare, export,
                    rescore, serve
```

## Eval Key Patterns

- **Model Adapters**: ABC in `execution/adapters/base.py`. Implement `async generate(prompt, params, options) -> GenerationResult`. Registry resolves by provider string.
- **Scorers**: ABC in `scoring/base.py`. Implement `score(output, expected) -> ScorerResult`. Registry in `_SCORER_REGISTRY`. Built-in scorers auto-register.
- **Orchestrator**: `execution/orchestrator.py` — `create_run()` → `execute_run()` → `score_run()`. Supports sequential and parallel modes via `asyncio.Semaphore`.
- **Service pattern**: Each service accepts `AsyncSession`, returns ORM instances. All CRUD is async. Versioning auto-increments `version_number`.
- **API pattern**: ORM objects converted to dicts BEFORE `session.commit()` to avoid MissingGreenlet. Service update methods call `await session.refresh(obj)` after flush on `onupdate` columns.
- **UI mounting**: `eval/ui/server.py` — `mount_ui(app)` registers templates and static files on the FastAPI app.

## Database Models

- `sources.py`: **Source**, **Page**, **Snapshot** — source catalog, monitored pages, HTML snapshots
- `events.py`: **EventRecord**, **ClaimRecord**, **CrossReference** — normalized events, per-source claims, inter-event links
- `research.py`: **CandidatePaper**, **EnrichedPaper** — research triage pipeline (candidate → enriched → promoted)

## Key Patterns

- **SourceCollector**: Abstract base in `sources/base.py`. Subclass and implement `extract_items(html: str, page: PageConfig) -> list[RawItem]`. Register in `sources/registry.py`.
- **BenchmarkCollector**: Extended base in `sources/benchmarks/__init__.py` with `extract_leaderboard()` returning `LeaderboardEntry` objects. Auto-converts to `RawItem` via default `extract_items()`.
- **Registry**: `COLLECTOR_CLASSES` dict in `sources/registry.py` maps org names to classes. `get_collector(source_config)` is the factory.
- **Processing pipeline**: `processing/pipeline.py` — `process_item()` / `process_items()` run the full normalize→dedup→verify→xref chain.
- **Scheduling**: `scheduling/scheduler.py` — `PipelineScheduler` wraps APScheduler with `SourceHealthTracker` circuit breaker (5 consecutive failures trips the breaker).
- **Reporting**: `reporting/query.py` for filtered event/claim queries; `reporting/export.py` for JSON/CSV serialization.
- **Async throughout**: SQLAlchemy async sessions, httpx async client, APScheduler AsyncIOScheduler.

## Polling Cadences

Defined in `config/schedules.toml`. Vendors every 6-12h, Reuters every 3h, benchmarks daily, research every 12h, community daily.

## Deduplication Strategy

Three-layer: (1) exact composite key `{normalized_title, org, source_type, path, date}`, (2) model slug + org + date, (3) fuzzy title match (0.85 threshold via SequenceMatcher). Cross-reference table links related records — do not flatten into a merged record.

## Configuration

Settings are loaded via `PipelineSettings` (Pydantic) with `AI_BENCH_` env prefix:

| Variable | Default | Purpose |
|---|---|---|
| `AI_BENCH_DATABASE_URL` | `sqlite+aiosqlite:///ai_benchmark.db` | Database connection |
| `AI_BENCH_LOG_LEVEL` | `INFO` | Logging level |
| `AI_BENCH_LOG_FORMAT` | `json` | `json` or `console` output |
| `AI_BENCH_GITHUB_TOKEN` | — | GitHub API access (Meta, GitHub discovery) |
| `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` | — | Semantic Scholar enrichment |
| `AI_BENCH_PROXY_URL` | — | HTTP proxy for fetcher |
| `AI_BENCH_REQUEST_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `AI_BENCH_MAX_CONCURRENCY` | `5` | Max concurrent requests |
| `AI_BENCH_RETRY_ATTEMPTS` | `3` | Fetch retry count |

Also supports `.env` file in project root.

## Key Design Constraints

- HTML diffing is the primary collection method; some sources use API access (Semantic Scholar, GitHub, Hugging Face)
- Research papers go through a triage pipeline (candidate → enrichment → authoritative store) — never auto-ingest
- Community sources ingest only minimal metadata (title, author, timestamp, tags, outbound links)
- Conflicts between sources are stored as separate claim records, not resolved automatically

## Requirements Documents

- Source details and intake guidance: `docs/core_requirements.md`
- Implementation plan (all phases complete): `docs/core_requirements_plan.md`
- Model eval pipeline design: `docs/model_eval_pipeline_design.md`
- Model eval pipeline PDR: `docs/model_eval_pipeline_pdr.md`
- Model eval pipeline plan: `docs/model_eval_pipeline_plan.md`
