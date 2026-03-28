# AI Benchmark Intelligence Pipeline

Monitors AI model releases, benchmark results, pricing changes, and research papers across 22 sources. Produces a structured local knowledge base of verified AI industry events with deduplication, verification hierarchy, and cross-referencing.

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

Environment variables use the `AI_BENCH_` prefix:

- `AI_BENCH_DATABASE_URL` — database connection (default: `sqlite+aiosqlite:///ai_benchmark.db`)
- `AI_BENCH_GITHUB_TOKEN` — GitHub API access for Meta and org discovery
- `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` — Semantic Scholar enrichment

Source catalog: `ai_benchmark/config/sources.toml` (22 sources, 48 pages)
Schedule config: `ai_benchmark/config/schedules.toml` (21 cron entries)

## Model Evaluation Pipeline (Planned)

A separate evaluation subsystem for comparing models across machines, runtimes, and configurations.

- Design: `docs/model_eval_pipeline_design.md`
- Physical requirements: `docs/model_eval_pipeline_pdr.md`
- Implementation plan: `docs/model_eval_pipeline_plan.md`

## Implementation Plans

- **Source pipeline:** `docs/core_requirements_plan.md` — All 7 phases complete
- **Eval pipeline:** `docs/model_eval_pipeline_plan.md` — 9 phases (E1–E9), not yet started

## Tests

```bash
pytest                       # Run all 163 tests
pytest tests/test_config.py  # Single test file
pytest -x                    # Stop on first failure
pytest -v                    # Verbose output
```
