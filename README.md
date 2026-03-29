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
                    ClaimRecord, CrossReference, CandidatePaper, EnrichedPaper)
  collection/       HTTP fetcher (httpx, retry/backoff), HTML differ, snapshot manager,
                    base API client
  sources/          Source-specific collectors (22 registered)
    openai.py, anthropic.py, google.py, xai.py, mistral.py, cohere.py, meta.py
    benchmarks/     Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE,
                    Terminal-Bench
    research/       arXiv, Semantic Scholar (collector + enrichment client), HF Papers
    news/           Reuters, TechCrunch
    community/      HF Forums, GitHub discovery, HF Leaderboard Docs
  processing/       Normalizer, deduplicator (composite key + model slug + fuzzy),
                    verification hierarchy (5 chains), cross-reference builder
                    (3 strategies: model-slug, org+event-type, arXiv ID → cites),
                    triage pipeline, quality filter, discovery queue (real fetch
                    execution), path prober, full processing pipeline
  scheduling/       APScheduler async scheduler, cron cadence config, health tracking
                    with circuit breaker
  reporting/        Query functions (events, claims, cross-refs), JSON/CSV export
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

Source catalog: `ai_benchmark/config/sources.toml` (22 sources, 78 pages)
Schedule config: `ai_benchmark/config/schedules.toml` (24 cron entries)

## Database Models

9 SQLAlchemy 2.0 async ORM models across 4 modules:

- **sources.py**: `Source`, `Page`, `Snapshot` — catalog, monitored pages, HTML content snapshots
- **events.py**: `EventRecord`, `ClaimRecord`, `CrossReference` — normalized events, per-source claims, inter-event links
- **research.py**: `CandidatePaper`, `EnrichedPaper` — research triage pipeline (discovered → enriched → promoted/rejected)
- **discovery.py**: `FollowUpTask` — model slug discovery queue follow-up tasks

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
  models/         18 SQLAlchemy tables (datasets, scorers, evaluations, targets,
                  machines, runners, runs, item results, metrics, artifacts,
                  traces, annotations)
  services/       14 async service modules (dataset, scorer, eval, machine, target,
                  runner, run, comparison, report, compatibility, seed, validation,
                  matrix, artifact)
  execution/      RunOrchestrator (with auto-artifact generation), ItemExecutor
                  (with trace capture), Dispatch engine, 12 model adapters
    adapters/     OpenAI, Anthropic, Local (legacy), GenericHTTP,
                  Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang,
                  TensorRT-LLM, OpenVINO GenAI
  scoring/        ScorerRunner + 8 built-in scorers (exact_match, fuzzy_match,
                  rubric, format_validator, latency_cost, safety, model_judge)
  api/            FastAPI with ~50 REST endpoints under /api/eval/,
                  API key auth middleware (X-API-Key / Bearer), /healthz
  ui/             Jinja2 templates: dashboard, entity pages, runner/run-group
                  pages, run detail/live, comparison, search, reports (22 templates)
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
~50 REST endpoints, API key auth, 10 CLI subcommands, 12 model adapters, 19 tables.
Runner/machine registry with compatibility rules and seed data for 7 target machines.

### Design Documents

- Eval pipeline design: `docs/model_eval_pipeline_design.md`
- Eval pipeline PDR: `docs/model_eval_pipeline_pdr.md`
- Eval pipeline plan: `docs/model_eval_pipeline_plan.md`
- Runner comparison PRD: `docs/llm_runner_prd.md`
- Runner comparison design: `docs/llm_runner_design.md`
- Runner comparison plan: `docs/llm_runner_plan.md`
- Naming conventions: `docs/naming_conventions.md`

## Implementation Plans

- **Source pipeline:** `docs/core_requirements_plan.md` — All 7 phases complete
- **Eval pipeline:** `docs/model_eval_pipeline_plan.md` — 9 phases (E1–E9) complete
- **Gap remediation v1:** `docs/gap_remediation_plan.md` — 6 phases (G1–G6), 66 tasks complete
- **Gap remediation v2:** `docs/gap_remediation_subset_plan_v2.md` — 13 tasks complete (discovery queue wiring, confidence tier fix, 5 new source pages, cross-ref cites + arXiv strategy, HLE multi-slice, LMArena image/vision, benchmark GitHub repos, Semantic Scholar dual classification)
- **PEP8 compliance:** `docs/pep8_plan.md` — All 7 phases complete
- **Runner comparison:** `docs/llm_runner_plan.md` — All 14 phases complete
- **Code review remediation:** `docs/general_code_review_plan.md` — All 4 phases complete (49 tasks)

## Development

```bash
pip install -e ".[dev]"      # Install with dev + test dependencies
pytest                       # Run all tests (666 tests, 0 failures)
pytest tests/test_config.py  # Single test file
pytest -x -v                 # Verbose, stop on first failure
ruff check .                 # Lint
mypy ai_benchmark            # Type check (strict mode)
```

Key dev dependencies: pytest, pytest-asyncio, respx (httpx mocking), httpx (API tests), ruff, mypy.

## License

MIT
