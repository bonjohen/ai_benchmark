# Analysis Pipeline — Implementation Plan

**Source document:** `docs/analysis_pipeline_pdr.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| ORM | SQLAlchemy 2.0 async (existing) |
| CLI | Click (existing) |
| API | FastAPI (existing) |
| Result types | stdlib dataclasses |
| Serialization | stdlib json, csv, io |
| Score extraction | stdlib re |
| Logging | structlog (existing) |
| Migration | Alembic (existing) |
| Testing | pytest + pytest-asyncio (existing) |

## Phase 1: Foundation

**Goal:** Package skeleton, ORM models, result dataclasses, migration, and CLI group registration exist. `ai-benchmark analyze --help` works.
**Depends on:** Nothing (first phase).

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:10 PM | Create `ai_benchmark/analysis/__init__.py` — empty package marker |
| 1.2 | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:12 PM | Create `ai_benchmark/analysis/models.py` — `AnalysisSnapshot` + `AnalysisInsight` ORM models per PDR §3.1-3.2 |
| 1.3 | Completed | 2026-03-29 06:12 PM | 2026-03-29 06:14 PM | Create `ai_benchmark/analysis/types.py` — all 15 result dataclasses per PDR §4 |
| 1.4 | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:10 PM | Create `ai_benchmark/analysis/services/__init__.py` — empty package marker |
| 1.5 | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:10 PM | Create `ai_benchmark/analysis/formatters/__init__.py` — empty package marker |
| 1.6 | Completed | 2026-03-29 06:14 PM | 2026-03-29 06:15 PM | Create `ai_benchmark/analysis/cli.py` — Click group `analyze` with `--help` only, no subcommands yet |
| 1.7 | Completed | 2026-03-29 06:15 PM | 2026-03-29 06:15 PM | Modify `ai_benchmark/cli.py` — register `analyze_group` after eval group (after line 276) |
| 1.8 | Completed | 2026-03-29 06:14 PM | 2026-03-29 06:15 PM | Create `alembic/versions/008_analysis_pipeline.py` — 2 tables + 7 indexes per PDR §3.3 |
| 1.9 | Completed | 2026-03-29 06:16 PM | 2026-03-29 06:18 PM | Create `tests/test_analysis/__init__.py` and `tests/test_analysis/conftest.py` with shared fixtures |
| 1.10 | Completed | 2026-03-29 06:18 PM | 2026-03-29 06:20 PM | Create `tests/test_analysis/test_models.py` — test ORM model creation and field defaults |
| 1.11 | Completed | 2026-03-29 06:18 PM | 2026-03-29 06:20 PM | Create `tests/test_analysis/test_types.py` — test dataclass instantiation and field types |
| 1.12 | Completed | 2026-03-29 06:20 PM | 2026-03-29 06:25 PM | Run `pytest` — 685 passed, 0 failures |
| 1.13 | Completed | 2026-03-29 06:22 PM | 2026-03-29 06:25 PM | Run `ruff check` + `ruff format --check` — clean |
| 1.14 | Open | | | Stage all Phase 1 changes |
| 1.15 | Open | | | Commit: "Add analysis pipeline foundation: models, types, migration, CLI skeleton" |

### Phase 1 Summary

- **Changes:** Created `ai_benchmark/analysis/` package with models (AnalysisSnapshot, AnalysisInsight), 15 result dataclasses, CLI skeleton, alembic migration 008 (2 tables + 7 indexes). Updated `tests/conftest.py` for model registration, `tests/test_migrations.py` for head revision. 19 new tests all passing. 685 total tests, 0 failures.
- **Changes hosted at:** TBD
- **Commit:** `Add analysis pipeline foundation: models, types, migration, CLI skeleton`

## Phase 2: Model Lifecycle Service + Formatters

**Goal:** `ai-benchmark analyze models` and `ai-benchmark analyze model <slug>` produce output in text/json/markdown formats. First working intelligence product.
**Depends on:** Phase 1.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Create `ai_benchmark/analysis/services/model_lifecycle.py` — `list_tracked_models`, `build_model_profile`, `get_model_timeline`, `compare_models` per PDR §5.1 |
| 2.2 | Open | | | Create `ai_benchmark/analysis/formatters/json_export.py` — `to_json()` with dataclasses.asdict support |
| 2.3 | Open | | | Create `ai_benchmark/analysis/formatters/markdown.py` — `model_profile_to_markdown`, `model_list_to_markdown` |
| 2.4 | Open | | | Create `ai_benchmark/analysis/formatters/csv_export.py` — `models_to_csv` |
| 2.5 | Open | | | Add CLI subcommands to `analysis/cli.py` — `analyze models` and `analyze model <slug>` with `--org`, `--format` options |
| 2.6 | Open | | | Create `tests/test_analysis/test_model_lifecycle.py` — service tests with sample EventRecord/ClaimRecord data |
| 2.7 | Open | | | Create `tests/test_analysis/test_formatters.py` — formatter output tests |
| 2.8 | Open | | | Run `pytest` — all tests pass |
| 2.9 | Open | | | Run `ruff check` + `ruff format --check` — clean |
| 2.10 | Open | | | Stage all Phase 2 changes |
| 2.11 | Open | | | Commit: "Add model lifecycle service with formatters and CLI commands" |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** TBD

## Phase 3: Benchmark Trends + Competitive Intelligence

**Goal:** `ai-benchmark analyze benchmark <name>`, `ai-benchmark analyze benchmarks`, and `ai-benchmark analyze competitive` work. Score extraction from raw content operational.
**Depends on:** Phase 2.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Create `ai_benchmark/analysis/services/benchmark_trends.py` — `extract_benchmark_score`, `list_benchmarks`, `get_benchmark_leaderboard`, `get_benchmark_timeline` per PDR §5.2 |
| 3.2 | Open | | | Create `ai_benchmark/analysis/services/competitive_intel.py` — `get_activity_timeline`, `detect_competitive_clusters`, `org_activity_summary` per PDR §5.3 |
| 3.3 | Open | | | Add formatters — `leaderboard_to_markdown`, `leaderboard_to_csv`, `activity_timeline_to_markdown` |
| 3.4 | Open | | | Add CLI subcommands — `analyze benchmarks`, `analyze benchmark <name>`, `analyze competitive` with options |
| 3.5 | Open | | | Create `tests/test_analysis/test_benchmark_trends.py` — score extraction tests + leaderboard tests |
| 3.6 | Open | | | Create `tests/test_analysis/test_competitive_intel.py` — cluster detection + activity timeline tests |
| 3.7 | Open | | | Run `pytest` — all tests pass |
| 3.8 | Open | | | Run `ruff check` + `ruff format --check` — clean |
| 3.9 | Open | | | Stage all Phase 3 changes |
| 3.10 | Open | | | Commit: "Add benchmark trends and competitive intelligence services" |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** TBD

## Phase 4: Research Pulse + Anomaly Detection

**Goal:** `ai-benchmark analyze research` and `ai-benchmark analyze anomalies` work. Anomaly insights are persisted to the database.
**Depends on:** Phase 3.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Create `ai_benchmark/analysis/services/research_pulse.py` — `get_research_trends`, `get_citation_leaders`, `detect_paper_to_product` per PDR §5.4 |
| 4.2 | Open | | | Create `ai_benchmark/analysis/services/anomaly_detector.py` — `detect_anomalies` with 6 rules + `get_recent_insights` per PDR §5.5 |
| 4.3 | Open | | | Add formatters — `research_trends_to_markdown`, `insights_to_markdown`, `insights_to_csv` |
| 4.4 | Open | | | Add CLI subcommands — `analyze research`, `analyze anomalies` with options |
| 4.5 | Open | | | Create `tests/test_analysis/test_research_pulse.py` — citation leaders, topic counts, paper-to-product tests |
| 4.6 | Open | | | Create `tests/test_analysis/test_anomaly_detector.py` — each rule tested, idempotency verified |
| 4.7 | Open | | | Run `pytest` — all tests pass |
| 4.8 | Open | | | Run `ruff check` + `ruff format --check` — clean |
| 4.9 | Open | | | Stage all Phase 4 changes |
| 4.10 | Open | | | Commit: "Add research pulse and anomaly detection services" |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** TBD

## Phase 5: Digest + API + Integration

**Goal:** `ai-benchmark analyze digest` and `ai-benchmark analyze run-all` work. REST API mounted at `/api/analysis/`. All products accessible via CLI, API, and formatters.
**Depends on:** Phase 4.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Create `ai_benchmark/analysis/services/digest.py` — `generate_digest` orchestrating all 5 services per PDR §5.6 |
| 5.2 | Open | | | Add `digest_to_markdown` formatter |
| 5.3 | Open | | | Add CLI subcommands — `analyze digest` (with `--format`, `--output`) and `analyze run-all` |
| 5.4 | Open | | | Create `ai_benchmark/analysis/api.py` — FastAPI router with 11 endpoints per PDR §8 |
| 5.5 | Open | | | Modify `ai_benchmark/eval/api/app.py` — import analysis models in lifespan, mount router at `/api/analysis` |
| 5.6 | Open | | | Create `tests/test_analysis/test_digest.py` — integration test: digest orchestrates all services |
| 5.7 | Open | | | Create `tests/test_analysis/test_cli.py` — CLI invocation tests via Click CliRunner |
| 5.8 | Open | | | Create `tests/test_analysis/test_api.py` — API endpoint tests via httpx AsyncClient |
| 5.9 | Open | | | Run `pytest` — all tests pass |
| 5.10 | Open | | | Run `ruff check` + `ruff format --check` — clean |
| 5.11 | Open | | | Stage all Phase 5 changes |
| 5.12 | Open | | | Commit: "Add digest service, REST API, and integration tests" |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** TBD

## Phase 6: Documentation + Final Verification

**Goal:** README and CLAUDE.md updated. Full regression passes. All 6 intelligence products operational end-to-end.
**Depends on:** Phase 5.

| # | Status | Started (PST) | Completed (PST) | Description |
|---|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Update `CLAUDE.md` — add Analysis Architecture section documenting package, services, CLI, API |
| 6.2 | Open | | | Update `README.md` — add Analysis Pipeline section with CLI examples |
| 6.3 | Open | | | Run full `pytest` — all existing 666+ plus new analysis tests pass |
| 6.4 | Open | | | Run `ruff check ai_benchmark/ tests/` + `ruff format --check ai_benchmark/ tests/` — clean |
| 6.5 | Open | | | Verify `ai-benchmark analyze --help` shows all subcommands |
| 6.6 | Open | | | Verify `alembic upgrade head` applies migration cleanly on fresh DB |
| 6.7 | Open | | | Stage all Phase 6 changes |
| 6.8 | Open | | | Commit: "Update documentation for analysis pipeline" |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** TBD
