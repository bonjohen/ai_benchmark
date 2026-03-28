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
  sources/          Source-specific collectors (21 registered)
    openai.py, anthropic.py, google.py, xai.py, mistral.py, cohere.py, meta.py
    benchmarks/     Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE,
                    Terminal-Bench
    research/       arXiv, Semantic Scholar (enrichment client), HF Papers
    news/           Reuters, TechCrunch
    community/      HF Forums, GitHub discovery, HF Leaderboard Docs
  processing/       Normalizer, deduplicator (composite key + fuzzy), verification
                    hierarchy (5 chains), cross-reference builder, triage pipeline,
                    full processing pipeline
  scheduling/       APScheduler async scheduler, cron cadence config, health tracking
                    with circuit breaker
  reporting/        Query functions (events, claims, cross-refs), JSON/CSV export
```

## Source Coverage

All 22 sources from the requirements are implemented:

| Category | Sources | Trust |
|---|---|---|
| Official vendors (7) | OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta | 4.5–5.0 |
| Benchmarks (7) | Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE, Terminal-Bench | 4.0–4.5 |
| Research feeds (3) | arXiv, Semantic Scholar, HF Papers | 4.0 |
| News (2) | Reuters (high secondary), TechCrunch (medium discovery) | 3.5–4.0 |
| Community (3) | HF Forums, GitHub discovery, HF Leaderboard Docs | 3.0 |

## Verification Hierarchy

Events are verified through 5 chains:

1. **Model releases**: Confirmed when 2+ official surfaces agree
2. **Benchmark claims**: Benchmark owner report required
3. **Pricing changes**: Only confirmed from pricing page changes
4. **Announcements**: Newsroom + at least one other source
5. **Research claims**: Primary paper required

Claims from different sources are stored as separate records — never merged.

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

Source catalog: `ai_benchmark/config/sources.toml` (22 sources, 48 pages)
Schedule config: `ai_benchmark/config/schedules.toml` (21 cron entries)

## Database Models

8 SQLAlchemy 2.0 async ORM models across 3 modules:

- **sources.py**: `Source`, `Page`, `Snapshot` — catalog, monitored pages, HTML content snapshots
- **events.py**: `EventRecord`, `ClaimRecord`, `CrossReference` — normalized events, per-source claims, inter-event links
- **research.py**: `CandidatePaper`, `EnrichedPaper` — research triage pipeline (discovered → enriched → promoted/rejected)

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
  models/         15 SQLAlchemy tables (datasets, scorers, evaluations, targets,
                  machines, runs, item results, metrics, artifacts)
  services/       8 async CRUD services (dataset, scorer, eval, machine, target,
                  run, comparison, report)
  execution/      RunOrchestrator, ItemExecutor, 4 model adapters (OpenAI,
                  Anthropic, Local, Generic HTTP)
  scoring/        ScorerRunner + 7 built-in scorers (exact_match, fuzzy_match,
                  rubric, format_validator, latency_cost, safety, model_judge)
  api/            FastAPI with ~45 REST endpoints under /api/eval/
  ui/             Jinja2 templates: dashboard, entity pages, run detail/live,
                  comparison view, reports with Chart.js
  cli/            9 Click subcommands (run, run-matrix, status, list, compare,
                  export, rescore, serve)
  config.py       EvalSettings with AI_BENCH_EVAL_ env prefix
```

### Eval Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AI_BENCH_EVAL_API_HOST` | `127.0.0.1` | API bind host |
| `AI_BENCH_EVAL_API_PORT` | `8100` | API bind port |
| `AI_BENCH_EVAL_ARTIFACT_STORAGE_PATH` | `./artifacts` | Artifact file storage |
| `AI_BENCH_EVAL_MAX_CONCURRENT_ITEMS` | `10` | Parallel item execution |
| `AI_BENCH_EVAL_DEFAULT_EXECUTION_MODE` | `sequential` | Default run mode |
| `AI_BENCH_EVAL_RUN_TIMEOUT_SECONDS` | `3600` | Per-run timeout |
| `AI_BENCH_EVAL_ITEM_TIMEOUT_SECONDS` | `120` | Per-item timeout |
| `AI_BENCH_EVAL_RETRY_FAILED_ITEMS` | `2` | Auto-retries per item |

### Design Documents

- Design: `docs/model_eval_pipeline_design.md`
- Physical requirements: `docs/model_eval_pipeline_pdr.md`
- Implementation plan: `docs/model_eval_pipeline_plan.md`

## Implementation Plans

- **Source pipeline:** `docs/core_requirements_plan.md` — All 7 phases complete
- **Eval pipeline:** `docs/model_eval_pipeline_plan.md` — 9 phases (E1–E9) complete

## Development

```bash
pip install -e ".[dev]"      # Install with dev + test dependencies
pytest                       # Run all 297 tests
pytest tests/test_config.py  # Single test file
pytest -x -v                 # Verbose, stop on first failure
ruff check .                 # Lint
mypy ai_benchmark            # Type check (strict mode)
```

Key dev dependencies: pytest, pytest-asyncio, respx (httpx mocking), httpx (API tests), ruff, mypy.

## License

MIT
