# AI Benchmark Intelligence Pipeline

Monitors AI model releases, benchmark results, pricing changes, and research papers across 22 sources. Produces a structured local knowledge base of verified AI industry events.

## Setup

```bash
pip install -e ".[dev]"
python -m ai_benchmark init-db
python -m ai_benchmark check-config
```

For research paper enrichment (Semantic Scholar, PDF parsing):

```bash
pip install -e ".[dev,research]"
```

## CLI

```bash
ai-benchmark init-db        # Create/migrate database schema
ai-benchmark check-config   # Validate source catalog and settings
ai-benchmark run             # Run collection pipeline (stub — Phase 7)
```

## Architecture

```
ai_benchmark/
  config/           Settings (Pydantic + env vars) and TOML source catalog
  models/           SQLAlchemy 2.0 async ORM (Source, Page, Snapshot, EventRecord,
                    ClaimRecord, CrossReference, CandidatePaper, EnrichedPaper)
  collection/       HTTP fetcher (httpx, retry/backoff), HTML differ, snapshot manager,
                    base API client
  sources/          Source-specific collectors
    openai.py, anthropic.py, google.py, xai.py, mistral.py, cohere.py, meta.py
    benchmarks/     Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE,
                    Terminal-Bench
    research/       arXiv, Semantic Scholar, HF Papers
    news/           (Phase 5)
    community/      (Phase 5)
  processing/       Normalizer (model slug extraction, event classification),
                    research triage pipeline (candidate → enrichment → promotion)
  scheduling/       (Phase 7)
  reporting/        (Phase 7)
```

## Source Coverage

| Category | Sources | Status |
|---|---|---|
| Official vendors (7) | OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta | Implemented |
| Benchmarks (7) | Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE, Terminal-Bench | Implemented |
| Research feeds (3) | arXiv, Semantic Scholar, HF Papers | Implemented |
| News (2) | Reuters, TechCrunch | Planned (Phase 5) |
| Community (3) | HF Forums, GitHub discovery, HF leaderboard docs | Planned (Phase 5) |

## Configuration

Environment variables use the `AI_BENCH_` prefix. Key settings:

- `AI_BENCH_DATABASE_URL` — database connection (default: `sqlite+aiosqlite:///ai_benchmark.db`)
- `AI_BENCH_GITHUB_TOKEN` — GitHub API access for Meta org monitoring
- `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` — Semantic Scholar API key

Source catalog is defined in `ai_benchmark/config/sources.toml` (22 sources, 48 pages).

## Model Evaluation Pipeline (Planned)

A separate evaluation subsystem for comparing models across machines, runtimes, and configurations. Covers evaluation definitions, dataset/scorer versioning, target configurations, run orchestration, side-by-side comparison, and a web UI.

- Design: `docs/model_eval_pipeline_design.md`
- Physical requirements: `docs/model_eval_pipeline_pdr.md`
- Implementation plan: `docs/model_eval_pipeline_plan.md`

## Implementation Plans

- **Source pipeline:** `docs/core_requirements_plan.md` — Phases 1–3 complete, 4–7 in progress
- **Eval pipeline:** `docs/model_eval_pipeline_plan.md` — 9 phases (E1–E9), not yet started

## Tests

```bash
pytest                       # Run all tests
pytest tests/test_config.py  # Single test file
pytest -x                    # Stop on first failure
```
