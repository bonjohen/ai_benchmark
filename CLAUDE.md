# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai_benchmark** is an AI model and benchmark intelligence pipeline. It monitors official AI company sources, benchmark leaderboards, research feeds, and news outlets to track model releases, pricing changes, benchmark results, and research papers. The system produces a structured local knowledge base of verified AI industry events.

## Build and Test

```bash
pip install -e ".[dev]"          # Install with dev dependencies
pip install -e ".[dev,research]" # Include research extras (S2, PDF)
pytest                           # Run all tests (666 pass, 0 failures)
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

- **Source catalog**: 22 monitored sources across 5 categories — 22 registered collectors (including SemanticScholarCollector); 87 monitored pages (including Google News RSS feeds and API endpoints)
- **Source classifications**: primary (official vendor pages), secondary (independent benchmarks, reputable news), discovery-only (community forums, arXiv, trending feeds)
- **Trust tiers**: sources rated 1-5; official vendor pages are 5, community sources as low as 3
- **Event records**: normalized change records with source, title, path, observed timestamp, and extracted model/version names
- **Claim records**: separate records per source for conflicting claims, with source_type, confidence tier, and cross-references — never merge conflicting claims prematurely
- **Confidence tiers** (5 standard values): `official_self_report` (primary vendors), `benchmark_owner_report` (benchmark sources), `high_secondary` (Reuters, Semantic Scholar metadata), `medium_discovery` (TechCrunch), `low_discovery` (forums, GitHub, Semantic Scholar discovery) — with source-specific overrides via `SOURCE_TIER_OVERRIDES` in `normalizer.py`
- **Discovery queue**: new model slugs trigger automatic follow-up tasks (pricing, release notes, system card, benchmark coverage); `execute_follow_up_tasks(session, fetcher, limit)` dispatches real page fetches and processes results through the standard pipeline
- **Quality filter**: low-value pages filtered at ingestion (trivial change ratio, stale dates, garbage titles)

## Verification Hierarchy

This ordering is load-bearing for the entire pipeline:

1. **Model releases**: vendor launch surface > developer docs/model catalog > pricing > changelog/release notes > system card. Confirmed when at least two official surfaces align on model name and availability.
2. **Benchmark claims**: always check the benchmark owner first, not the vendor. Record variant (e.g., SWE-bench Verified vs Lite vs Pro) and evaluation conditions.
3. **Pricing changes**: only confirmed when the official pricing page changes. Store HTML snapshot + observation timestamp.
4. **Company announcements**: company newsroom/press first, then docs/product page, then Reuters, then other outlets.
5. **Research claims**: primary paper (arXiv/publisher) first, then Semantic Scholar metadata, then company blog narrative. Blog alone never confirms a technical claim.

## Processing Pipeline

Each collected item goes through: normalize → discovery check → deduplicate → create event → create claim → update confirmation status → build cross-references. Research items (`candidate_paper`) are routed through the triage pipeline instead. New model slugs trigger follow-up task creation and real page fetches via `execute_follow_up_tasks(session, fetcher)`. Low-value pages are filtered at ingestion. Duplicates from different sources still create claims on the existing event, enabling multi-source confirmation.

## Architecture

```
ai_benchmark/
  config/           Pydantic settings (env vars), TOML source catalog + schedule definitions
  models/           SQLAlchemy 2.0 async ORM — 9 models across 4 modules
  collection/       HTTP fetcher (httpx, retry/backoff), HTML differ, snapshot manager, API client
  sources/          22 registered source collectors (HTML + RSS + API collection methods)
    benchmarks/     7 benchmark collectors (Artificial Analysis, LMArena, LiveBench, SWE-bench,
                    GAIA, HLE, Terminal-Bench) — HTML + Google News RSS fallback
    research/       arXiv (HTML), Semantic Scholar (API via collect_page override), HF Papers (HTML)
    news/           Reuters (Google News RSS), TechCrunch (WordPress RSS + HTML)
    community/      HF Forums (Discourse JSON API + HTML), GitHub discovery (GitHub API via
                    collect_page override), HF Leaderboard Docs (HTML)
    base.py         SourceCollector ABC with shared _extract_google_news_rss() helper
  processing/       Normalizer, deduplicator, verification, cross-reference builder, triage,
                    quality filter, discovery queue, path prober, pipeline orchestrator
  scheduling/       APScheduler async scheduler, cron cadence config, health tracker with circuit breaker
  reporting/        Query functions (events, claims, cross-refs, research counts), JSON/CSV export
  eval/             Model evaluation pipeline (see Eval Architecture below)
```

## Eval Architecture

```
ai_benchmark/eval/
  config.py         EvalSettings with AI_BENCH_EVAL_ env prefix
  models/           19 SQLAlchemy tables: datasets, dataset_versions, test_cases, scorers,
                    scorer_versions, evaluation_definitions, evaluation_versions, machine_profiles,
                    machine_snapshots, target_configurations, runner_profiles, run_groups, runs,
                    run_item_results, run_aggregate_metrics, artifacts, trace_references,
                    annotations, eval_audit_log
  services/         16 async service modules: dataset, scorer, eval, machine, target, runner,
                    run, comparison, report, compatibility, seed, validation, matrix, artifact,
                    audit, privacy — all accept AsyncSession, return model instances
  execution/        RunOrchestrator (3-stage: create → execute → score/finalize),
                    ItemExecutor (prompt templating, retry), 13 model adapters
    adapters/       OpenAI, Anthropic, Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang,
                    TensorRT-LLM, OpenVINO GenAI, GenericHTTP, OpenAI-compat, Local (legacy)
  scoring/          ScorerRunner (weighted pass logic, aggregate metrics), BaseScorer ABC
    builtin/        7 scorers: exact_match, fuzzy_match, rubric, format_validator,
                    latency_cost, safety, model_judge
  api/              FastAPI app factory, ~50 endpoints under /api/eval/,
                    API key auth middleware (X-API-Key / Bearer), /healthz
    routes/         9 route modules: evaluations, datasets, scorers, targets, machines,
                    runs, runners, comparisons, reports
    schemas/        Pydantic request/response models for all entities
  ui/               Jinja2 server-rendered UI with sectioned sidebar navigation
    templates/      28 HTML templates: dashboard, entity list/detail/create/clone/preview,
                    runner/run-group pages, run detail/live/launch, comparison, search,
                    reports with Chart.js, includes (empty_state, metadata_panel)
    static/         CSS (tables, cards, badges, metadata panel, empty states) + JS
                    (sorting, tabs, auto-refresh, search)
  cli/              10 Click subcommands: run, run-matrix, status, list, compare, export,
                    rescore, serve, runners, machines
```

## Eval Key Patterns

- **Model Adapters**: ABC in `execution/adapters/base.py`. Implement `async generate(prompt, params, options) -> GenerationResult`. Registry resolves by provider string. 13 adapters: OpenAI, Anthropic, Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, OpenVINO GenAI, GenericHTTP, OpenAI-compat, Local (legacy).
- **Scorers**: ABC in `scoring/base.py`. Implement `score(output, expected) -> ScorerResult`. Registry in `_SCORER_REGISTRY`. Built-in scorers auto-register. 7 scorers: exact_match, fuzzy_match, rubric, format_validator, latency_cost, safety, model_judge.
- **Orchestrator**: `execution/orchestrator.py` — `create_run()` → `execute_run()` → `score_run()`. Supports sequential and parallel modes via `asyncio.Semaphore`.
- **Service pattern**: Each service accepts `AsyncSession`, returns ORM instances. All CRUD is async. Versioning auto-increments `version_number`. 16 services: dataset, scorer, eval, machine, target, runner, run, comparison, report, compatibility, seed, validation, matrix, artifact, audit, privacy.
- **API pattern**: ORM objects converted to dicts BEFORE `session.commit()` to avoid MissingGreenlet. Service update methods call `await session.refresh(obj)` after flush on `onupdate` columns.
- **UI mounting**: `eval/ui/server.py` — `mount_ui(app)` registers templates and static files on the FastAPI app.

## Database Models

- `sources.py`: **Source**, **Page**, **Snapshot** — source catalog, monitored pages, HTML snapshots
- `events.py`: **EventRecord**, **ClaimRecord**, **CrossReference** — normalized events, per-source claims, inter-event links
- `research.py`: **CandidatePaper**, **EnrichedPaper** — research triage pipeline (candidate → enriched → promoted)
- `discovery.py`: **FollowUpTask** — model slug discovery follow-up tasks

## Key Patterns

- **SourceCollector**: Abstract base in `sources/base.py`. Subclass and implement `extract_items(html: str, page: PageConfig) -> list[RawItem]`. Register in `sources/registry.py`. Base class provides `_extract_google_news_rss()` helper. API-based collectors override `collect_page()` instead.
- **BenchmarkCollector**: Extended base in `sources/benchmarks/__init__.py` with `extract_leaderboard()` returning `LeaderboardEntry` objects. Auto-converts to `RawItem` via default `extract_items()`.
- **Registry**: `COLLECTOR_CLASSES` dict in `sources/registry.py` maps org names to classes. `get_collector(source_config)` is the factory. Passes `github_token` and `semantic_scholar_api_key` to collectors that need them.
- **Collection methods**: Three patterns — (1) HTML fetch + extract_items for standard pages, (2) Google News RSS feeds for Cloudflare-blocked or JS-rendered sites, (3) API calls via `collect_page()` overrides for GitHub, Meta, and Semantic Scholar.
- **Processing pipeline**: `processing/pipeline.py` — `process_item()` / `process_items()` run the full normalize→dedup→verify→xref chain. `candidate_paper` items are routed through the triage pipeline instead.
- **Scheduling**: `scheduling/scheduler.py` — `PipelineScheduler` wraps APScheduler with `SourceHealthTracker` circuit breaker (5 consecutive failures trips the breaker).
- **Reporting**: `reporting/query.py` for filtered event/claim queries and research paper counts; `reporting/export.py` for JSON/CSV serialization.
- **Async throughout**: SQLAlchemy async sessions, httpx async client, APScheduler AsyncIOScheduler.

## Polling Cadences

Defined in `config/schedules.toml`. Vendors every 6-12h, Reuters every 3h, benchmarks daily, research every 12h, community daily.

## Deduplication Strategy

Three-layer: (1) exact composite key `{normalized_title, org, source_type, path, date, model_slug}`, (2) model slug + org + date, (3) fuzzy title match (0.85 threshold via SequenceMatcher). Cross-reference table links related records — do not flatten into a merged record.

## Cross-Reference Strategies

Three strategies in `processing/cross_reference.py` → `build_cross_references()`:
1. **Model slug + time window** — same model mentioned by different sources within 7 days → `confirms` or `supplements`
2. **Org + event type** — same org, same event type within 3 days → `supplements`
3. **arXiv ID** — shared arXiv ID in title or `raw_content` → `cites`

Relationship types: `confirms`, `supplements`, `conflicts_with`, `cites`. Conflict detection uses >10% numerical disagreement between claims.

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

- Three collection methods: HTML diffing (primary), Google News RSS feeds (for Cloudflare-blocked or JS-rendered sites), API calls (GitHub, Semantic Scholar, Discourse)
- API-based collectors override `collect_page()` to call their API methods directly instead of fetching HTML
- Research papers go through a triage pipeline (candidate → enrichment → authoritative store) — never auto-ingest; show as "Papers" not "Events" in status
- Community sources ingest only minimal metadata (title, author, timestamp, tags, outbound links)
- Conflicts between sources are stored as separate claim records, not resolved automatically

## Linting

Codebase is fully compliant with ruff (E/F/I/N/W/UP/B/SIM/TCH rules, line-length 100, py312). Run `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — both exit clean. Per-file-ignores for B008 (FastAPI Depends pattern) in `eval/api/routes/*.py` and `eval/ui/server.py`. Some model/schema files have `# noqa: TC003` for datetime imports required at runtime by SQLAlchemy/Pydantic.

## Documentation

Active docs in `docs/`:
- Naming conventions: `docs/naming_conventions.md`
- Eval automation examples: `docs/eval_automation_examples.md`
- Collection bug tracker: `docs/collection_bugs.md`

Archived plans and design docs in `docs/archive/`:
- Source requirements: `docs/archive/core_requirements.md`
- All implementation plans (core, eval, gap remediation, PEP8, runner comparison, code review)
- All design docs (eval pipeline design/PDR, runner comparison PRD/design)
- Gap analyses and release notes
