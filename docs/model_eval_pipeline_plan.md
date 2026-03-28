# Model Evaluation Pipeline — Implementation Plan

**Source document:** `docs/model_eval_pipeline_pdr.md`

## Work Queue Instructions

This document is the execution work queue for building the Model Evaluation Pipeline. Each phase is a self-contained deliverable. Tasks within a phase may be worked in order or parallelized where dependencies allow.

### State Transitions

```
Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed
```

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the task description. Move back to Started once unblocked.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task in the phase reaches `Completed`, write the **Phase Summary** section at the end of that phase.
3. Stage and commit all changes for the phase: `git add . && git commit -m "Eval Phase EN: <short description>"`. **Do not push.**
4. Proceed immediately to the next phase. Velocity is the priority — do not wait for review between phases unless blocked.

### Final Phase Protocol

After the last phase is committed, update `README.md` and `CLAUDE.md` with eval pipeline documentation. Commit that separately.

### Server Link Convention

Each phase summary includes a `Changes hosted at:` field. Populate with the URL to the commit or deployment once available. Leave as `TBD` until pushed/deployed.

---

## Technology Stack (Additive)

These are additions to the existing pipeline stack.

| Concern | Choice |
|---|---|
| API framework | `FastAPI >=0.110` |
| ASGI server | `uvicorn[standard] >=0.27` |
| Templating | `Jinja2 >=3.1` |
| File uploads | `python-multipart >=0.0.9` |
| Model adapters | `httpx` (existing), `openai` SDK, `anthropic` SDK |
| Testing (API) | `httpx` + FastAPI `TestClient` |
| Config | `EvalSettings(BaseSettings)` with `AI_BENCH_EVAL_` env prefix |

---

## Phase E1: Data Models, Migration, and Model Unit Tests

**Goal:** Create all 15 database tables for the evaluation subsystem, the Alembic migration, and unit tests verifying schema correctness. After this phase, `ai-benchmark init-db` creates all eval tables and tests confirm every FK, unique constraint, and JSON field round-trip.

**Depends on:** Existing Phase 1 infrastructure (Base, create_engine, session factory, Alembic).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E1.1 | Completed | 2026-03-28 08:30 PST | 2026-03-28 08:31 PST | Create `ai_benchmark/eval/__init__.py` and `ai_benchmark/eval/models/__init__.py`. Establish the eval package root. |
| E1.2 | Completed | 2026-03-28 08:31 PST | 2026-03-28 08:33 PST | Implement `eval/models/dataset.py` — `Dataset`, `DatasetVersion`, `TestCase` tables with FK constraints, unique constraint on `(dataset_id, version_number)`, index on `(dataset_version_id, item_index)`. JSON fields for `metadata`, `tags`. |
| E1.3 | Completed | 2026-03-28 08:33 PST | 2026-03-28 08:34 PST | Implement `eval/models/scorer.py` — `Scorer`, `ScorerVersion` tables with unique constraint on `(scorer_id, version_number)`. JSON `config` field with scorer-type-specific parameters. `implementation_ref` for module path. |
| E1.4 | Completed | 2026-03-28 08:34 PST | 2026-03-28 08:36 PST | Implement `eval/models/evaluation.py` — `EvaluationDefinition`, `EvaluationVersion` tables. FK to `dataset_versions`. JSON fields for `scorer_config`, `preprocessing`, `pass_criteria`. Unique constraint on `(evaluation_id, version_number)`. |
| E1.5 | Completed | 2026-03-28 08:36 PST | 2026-03-28 08:37 PST | Implement `eval/models/machine.py` — `MachineProfile`, `MachineSnapshot` tables. JSON fields for `accelerator_details`, `runtime_availability`, `snapshot_data`. Unique constraint on `hostname`. |
| E1.6 | Completed | 2026-03-28 08:37 PST | 2026-03-28 08:38 PST | Implement `eval/models/target.py` — `TargetConfiguration` table with FK to `machine_profiles`. JSON fields for `inference_params`, `runtime_options`, `tags`. Unique constraint on `name`. |
| E1.7 | Completed | 2026-03-28 08:38 PST | 2026-03-28 08:40 PST | Implement `eval/models/run.py` — `RunGroup`, `Run`, `RunItemResult`, `RunAggregateMetric` tables. Run has FK to `evaluation_versions`, `target_configurations`, `machine_snapshots`, `dataset_versions`, `run_groups`. Item results have FK to `runs` and `test_cases`. Aggregate metrics have unique constraint on `(run_id, metric_name)`. Indexes on `(run_id, item_index)` and `(run_id, overall_pass)`. |
| E1.8 | Completed | 2026-03-28 08:40 PST | 2026-03-28 08:41 PST | Implement `eval/models/artifact.py` — `Artifact` table with FK to `runs`. Fields for `artifact_type`, `filename`, `file_path`, `size_bytes`, `mime_type`. |
| E1.9 | Completed | 2026-03-28 08:41 PST | 2026-03-28 08:44 PST | Create Alembic migration `alembic/versions/002_evaluation_pipeline.py` — create all 15 tables in dependency order: datasets → dataset_versions → test_cases → scorers → scorer_versions → evaluation_definitions → evaluation_versions → machine_profiles → machine_snapshots → target_configurations → run_groups → runs → run_item_results → run_aggregate_metrics → artifacts. |
| E1.10 | Completed | 2026-03-28 08:44 PST | 2026-03-28 08:50 PST | Write `tests/test_eval/test_eval_models.py` — 35 tests covering all 15 tables: CRUD, FK constraints, unique constraints, JSON field round-trips. Extended `conftest.py` with `db_engine_fk` fixture for FK enforcement. |

### Phase E1 Summary

- **Changes:** Created `ai_benchmark/eval/` package with 7 model modules defining all 15 evaluation tables. Added Alembic migration `002_evaluation_pipeline.py`. Extended `tests/conftest.py` with FK-enforcing engine fixture. Added 35 model tests in `tests/test_eval/test_eval_models.py`. Updated `alembic/env.py` to import eval models. Full test suite: 198 tests passing.
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E1: Data models, migration, and model unit tests`

---

## Phase E2: Service Layer (CRUD for All Entities)

**Goal:** Implement async service classes providing CRUD operations, versioning, cloning, and filtering for all evaluation entities. After this phase, all business logic is testable without API or UI.

**Depends on:** E1 (all model classes and tables).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E2.1 | Completed | 2026-03-28 08:52 PST | 2026-03-28 08:52 PST | Create `eval/services/__init__.py`. Establish convention: each service accepts `AsyncSession`, returns model instances or lists. |
| E2.2 | Completed | 2026-03-28 08:52 PST | 2026-03-28 08:55 PST | Implement `eval/services/dataset_service.py` — `create_dataset()`, `list_datasets()`, `get_dataset()`, `create_version()` (auto-increments version_number, computes checksum, sets item_count), `get_version()`, `list_items()` with metadata tag/difficulty/modality filters, `filter_items()` by metadata query. |
| E2.3 | Completed | 2026-03-28 08:55 PST | 2026-03-28 08:56 PST | Implement `eval/services/scorer_service.py` — `create_scorer()`, `list_scorers()` with type filter, `get_scorer()`, `create_version()` (auto-increments), `get_version()`. |
| E2.4 | Completed | 2026-03-28 08:56 PST | 2026-03-28 08:58 PST | Implement `eval/services/eval_service.py` — `create_evaluation()`, `list_evaluations()` with name/tag/archive filters, `get_evaluation()`, `update_evaluation()`, `create_version()` (validates dataset_version_id and scorer_config references exist), `get_version()`. |
| E2.5 | Completed | 2026-03-28 08:58 PST | 2026-03-28 09:00 PST | Implement `eval/services/machine_service.py` — `create_profile()`, `list_profiles()` with hardware_class/hostname filters, `get_profile()`, `update_profile()`, `capture_snapshot()` (copies current profile fields + runtime metadata into MachineSnapshot JSON). |
| E2.6 | Completed | 2026-03-28 09:00 PST | 2026-03-28 09:02 PST | Implement `eval/services/target_service.py` — `create_target()`, `list_targets()` with model/provider/machine/hardware_class/archive filters, `get_target()`, `update_target()`, `clone_target()` (copies all fields, applies overrides, assigns new name). |
| E2.7 | Completed | 2026-03-28 09:02 PST | 2026-03-28 09:05 PST | Implement `eval/services/run_service.py` — `create_run()` (validates refs, captures machine snapshot, sets status=queued), `create_batch()` (creates RunGroup + N runs), `get_run()`, `list_runs()` with filters for evaluation/target/machine/status/model/hardware_class/date_range/tags, `update_status()`, `cancel_run()`, `get_item_results()` with pass/scorer/latency filters, `get_metrics()`, `list_artifacts()`. |
| E2.8 | Completed | 2026-03-28 09:05 PST | 2026-03-28 09:07 PST | Implement `eval/services/comparison_service.py` — `compare_runs()` (loads aggregate metrics for each run, computes per-metric deltas, per-scorer breakdown, item-level diffs for shared test cases), `diff_target_configs()` (field-level comparison of 2+ targets, returns only differing fields). |
| E2.9 | Completed | 2026-03-28 09:07 PST | 2026-03-28 09:10 PST | Implement `eval/services/report_service.py` — `generate_summary()` with group_by (evaluation/model_family/machine/date_range) and metric selection, `list_presets()`, `save_preset()`, `run_preset()`. Export helpers for JSON, CSV, HTML. |
| E2.10 | Completed | 2026-03-28 09:10 PST | 2026-03-28 09:15 PST | Write `tests/test_eval/test_dataset_service.py` (10 tests) — dataset + version CRUD, test case insertion and count, metadata tag filtering, checksum computation. Write `tests/test_eval/test_comparison_service.py` (6 tests) — two-run and three-run comparison, metric deltas, item-level diff, config diff. |

### Phase E2 Summary

- **Changes:** Created 8 service modules in `ai_benchmark/eval/services/`: dataset_service, scorer_service, eval_service, machine_service, target_service, run_service, comparison_service, report_service. All implement async CRUD with filtering, versioning auto-increment, and JSON field handling. Added 16 service tests across 2 test files. Full test suite: 214 tests passing.
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E2: Service layer with CRUD, versioning, and comparison logic`

---

## Phase E3: Execution Engine (Orchestrator and Model Adapters)

**Goal:** Implement the run orchestrator and all four model adapter types. After this phase, a run can be created, executed against any supported model endpoint, and item results are captured with latency/token/cost metadata.

**Depends on:** E2 (run_service, target_service, dataset_service).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E3.1 | Completed | 2026-03-28 | 2026-03-28 | Create `eval/execution/__init__.py` and `eval/execution/adapters/__init__.py`. |
| E3.2 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/adapters/base.py` — `ModelAdapter` ABC with `async generate(prompt, inference_params, runtime_options) -> GenerationResult`. `GenerationResult` dataclass: `output_text`, `raw_response`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_estimate_usd`, `trace_id`, `retry_count`, `error`. Adapter factory function `resolve_adapter(provider) -> ModelAdapter`. |
| E3.3 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/adapters/openai_adapter.py` — `OpenAIAdapter(ModelAdapter)`. Uses httpx to call OpenAI-compatible chat completions API. Maps `inference_params` to API fields. Extracts usage tokens, computes latency, estimates cost. Handles rate limit retries. |
| E3.4 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/adapters/anthropic_adapter.py` — `AnthropicAdapter(ModelAdapter)`. Calls Anthropic messages API. Maps inference_params (temperature, max_tokens, top_p, stop_sequences). Extracts input/output token counts. |
| E3.5 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/adapters/local_adapter.py` — `LocalAdapter(ModelAdapter)`. Calls local HTTP server (Ollama, vLLM, llama.cpp) using OpenAI-compatible chat format. Handles connection errors, timeout, local-only mode enforcement. |
| E3.6 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/adapters/generic_http_adapter.py` — `GenericHTTPAdapter(ModelAdapter)`. User-configurable request/response field mapping via `runtime_options`. Supports arbitrary REST endpoints. |
| E3.7 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/executor.py` — `ItemExecutor` class. For a single test case: resolves adapter from target config provider, applies prompt_wrapper and prompt_template from evaluation version, calls `adapter.generate()`, captures `GenerationResult`, creates/updates `RunItemResult` row. Handles per-item timeout and retry (up to `retry_failed_items` from EvalSettings). |
| E3.8 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/execution/orchestrator.py` — `RunOrchestrator` class. Three-stage flow: `create_run()` (validate refs, capture snapshot, enqueue), `execute_run(run_id)` (load items, iterate through executor, update counters), `finalize_run(run_id)` (set terminal status, completed_at, generate default artifacts). Supports sequential and parallel execution modes via `execution_mode` setting. Updates `run.completed_items` / `run.failed_items` after each item. |
| E3.9 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/config.py` — `EvalSettings(BaseSettings)` with `AI_BENCH_EVAL_` env prefix: `api_host`, `api_port`, `artifact_storage_path`, `max_concurrent_items`, `default_execution_mode`, `run_timeout_seconds`, `item_timeout_seconds`, `retry_failed_items`, `enable_cost_tracking`, `local_only_mode`. |
| E3.10 | Completed | 2026-03-28 | 2026-03-28 | Write `tests/test_eval/test_executor.py` — adapter resolution by provider string, prompt template application, mock model calls returning GenerationResult, error capture and retry behavior. Write `tests/test_eval/test_orchestrator.py` — full run lifecycle (queued → running → completed), partial failure handling (1 of N items fails → partially_completed), matrix run creation via create_batch. |

### Phase E3 Summary

- **Changes:** Execution engine with 4 model adapters (OpenAI, Anthropic, Local, Generic HTTP), ItemExecutor with prompt templating and retry, RunOrchestrator with sequential/parallel modes and lifecycle management, EvalSettings configuration, 20 new tests (234 total).
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E3: Execution engine with orchestrator and model adapters`

---

## Phase E4: Scoring Engine (Scorer Runner and Built-in Scorers)

**Goal:** Implement the scorer dispatch system and all 7 built-in scorer types. After this phase, a completed run can be scored, item-level results contain scorer outputs, and aggregate metrics are computed.

**Depends on:** E3 (orchestrator writes RunItemResults that scoring reads).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E4.1 | Completed | 2026-03-28 | 2026-03-28 | Create `eval/scoring/__init__.py` and `eval/scoring/builtin/__init__.py`. |
| E4.2 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/exact_match.py` — `ExactMatchScorer(BaseScorer)` and `FuzzyMatchScorer(BaseScorer)`. Exact match supports `case_sensitive`, `strip_whitespace`, `normalize_unicode`. Fuzzy match supports `threshold` (0.0–1.0) and `method` ("levenshtein" via difflib.SequenceMatcher, "token_overlap"). Score is 1.0 or 0.0 for exact; 0.0–1.0 for fuzzy. |
| E4.3 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/rubric.py` — `RubricScorer(BaseScorer)`. Config: `rubric_text`, `scale_min`, `scale_max`, `pass_threshold`. Evaluates output against rubric criteria. Returns score on scale, pass if >= threshold. Details include per-dimension scores if rubric is multi-dimensional. |
| E4.4 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/format_validator.py` — `FormatValidatorScorer(BaseScorer)`. Config: `expected_format` ("json", "xml", "markdown", "code"), optional `schema` (JSON Schema). Score 1.0 if valid, 0.0 if not. Details include validation errors. |
| E4.5 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/latency_cost.py` — `LatencyCostScorer(BaseScorer)`. Config: `latency_threshold_ms`, `cost_threshold_usd`, `token_budget`. Reads item_result metadata (latency_ms, cost_estimate_usd, total_tokens). Score = weighted pass on thresholds. |
| E4.6 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/safety.py` — `SafetyScorer(BaseScorer)`. Config: `categories` (list of safety categories), `threshold`. Keyword/pattern-based check for harmful content categories. Score 1.0 if safe, 0.0 if flagged. |
| E4.7 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/builtin/model_judge.py` — `ModelJudgeScorer(BaseScorer)`. Config: `judge_model`, `judge_endpoint`, `judge_params`, `judge_prompt_template`, `scale_min`, `scale_max`, `pass_threshold`. Calls a judge model (via adapter) with the input/output/expected to produce a score. Async. Stores judge response in details. |
| E4.8 | Completed | 2026-03-28 | 2026-03-28 | Implement `eval/scoring/scorer_runner.py` — `ScorerRunner` class. Loads scorer_config from evaluation version (list of `{scorer_version_id, weight, pass_threshold}`). For each RunItemResult, dispatches to each scorer, appends results to `scorer_results` JSON, computes `overall_pass` using weighted pass logic. After all items, computes `RunAggregateMetric` rows: overall pass_rate, per-scorer pass_rate and avg_score, avg_latency_ms, total_cost_usd, p50/p95/p99 latency. |
| E4.9 | Completed | 2026-03-28 | 2026-03-28 | Wire scoring into orchestrator — `orchestrator.score_run(run_id)`: sets status=scoring, invokes `ScorerRunner`, computes aggregates, then calls `finalize_run()`. |
| E4.10 | Completed | 2026-03-28 | 2026-03-28 | Write `tests/test_eval/test_scorer_runner.py` — test each built-in scorer individually with known inputs. Test scorer_runner dispatch with multi-scorer config. Test aggregate metric computation. Test model_judge scorer with mocked adapter. |

### Phase E4 Summary

- **Changes:** Scoring engine with BaseScorer ABC, 7 built-in scorers (exact_match, fuzzy_match, rubric, format_validator, latency_cost, safety, model_judge), ScorerRunner with weighted pass logic and aggregate metrics, orchestrator integration. 26 new tests (260 total).
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E4: Scoring engine with 7 built-in scorers and aggregate metrics`

---

## Phase E5: FastAPI Routes and Pydantic Schemas

**Goal:** Expose the full REST API described in PDR Section 4. All 8 endpoint groups (~30 endpoints) with request validation, response serialization, and error handling. After this phase, all operations are available programmatically.

**Depends on:** E2 (service layer). Can be developed in parallel with E3/E4 for non-run endpoints.

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E5.1 | Open | — | — | Create `eval/api/__init__.py`, `eval/api/routes/__init__.py`, `eval/api/schemas/__init__.py`. Implement `eval/api/app.py` — FastAPI app factory with lifespan (DB engine setup, session dependency), CORS, exception handlers. Mount all route groups under `/api/eval`. |
| E5.2 | Open | — | — | Implement `eval/api/schemas/evaluation.py` — Pydantic request/response models: `EvaluationCreate`, `EvaluationUpdate`, `EvaluationResponse`, `EvaluationVersionCreate`, `EvaluationVersionResponse`. JSON field handling for `scorer_config`, `preprocessing`, `pass_criteria`. |
| E5.3 | Open | — | — | Implement `eval/api/schemas/dataset.py` — `DatasetCreate`, `DatasetResponse`, `DatasetVersionCreate` (with items list), `DatasetVersionResponse`, `TestCaseResponse`, `ItemFilterRequest`. |
| E5.4 | Open | — | — | Implement `eval/api/schemas/scorer.py`, `target.py`, `machine.py` — request/response models for scorers (with type-specific config validation), targets (with clone overrides), machines (with snapshot capture body). |
| E5.5 | Open | — | — | Implement `eval/api/schemas/run.py` — `RunCreate`, `RunBatchCreate`, `RunResponse`, `RunItemResultResponse`, `RunMetricResponse`, `RescoreRequest`. `eval/api/schemas/comparison.py` — `CompareRequest`, `CompareResponse`, `ConfigDiffRequest`, `ConfigDiffResponse`. `eval/api/schemas/report.py` — `ReportRequest`, `PresetCreate`, `PresetResponse`. |
| E5.6 | Open | — | — | Implement `eval/api/routes/evaluations.py` — 6 endpoints: list, create, get, update, create version, get version. All with query parameter filters, pagination (limit/offset/sort/order). |
| E5.7 | Open | — | — | Implement `eval/api/routes/datasets.py` — 7 endpoints: list, create, get, create version, get version, list items (with pagination + filters), filter items. `eval/api/routes/scorers.py` — 4 endpoints: list, create, get, create version. |
| E5.8 | Open | — | — | Implement `eval/api/routes/targets.py` — 5 endpoints: list, create, get, update, clone. `eval/api/routes/machines.py` — 5 endpoints: list, create, get, update, snapshot. |
| E5.9 | Open | — | — | Implement `eval/api/routes/runs.py` — 12 endpoints: list, create, batch create, get detail, list items, get item, get metrics, list artifacts, download artifact, cancel, retry, rescore. `eval/api/routes/comparisons.py` — 2 endpoints: compare runs, config diff. `eval/api/routes/reports.py` — 4 endpoints: generate summary, list presets, save preset, run preset. |
| E5.10 | Open | — | — | Add `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart` to `pyproject.toml` dependencies. |
| E5.11 | Open | — | — | Write `tests/test_eval/test_api/test_evaluations_api.py` — CRUD endpoints, version creation, validation errors, pagination. Write `tests/test_eval/test_api/test_runs_api.py` — run creation, batch creation, status transitions, item listing, cancel, retry, rescore. Write `tests/test_eval/test_api/test_comparisons_api.py` — comparison endpoint, config diff endpoint. |

### Phase E5 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E5: FastAPI routes, Pydantic schemas, and API tests`

---

## Phase E6: CLI Commands

**Goal:** Add the `eval` subcommand group to the existing Click CLI. After this phase, all core eval operations are available from the terminal: triggering runs, checking status, comparing, exporting, and starting the server.

**Depends on:** E3, E4, E5 (execution engine, scoring, API server).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E6.1 | Open | — | — | Create `eval/cli/__init__.py` and `eval/cli/commands.py`. Register `eval` as a Click subgroup on the main `cli` group in `ai_benchmark/cli.py`. |
| E6.2 | Open | — | — | Implement `eval run` command — `--evaluation <name_or_id>`, `--target <name_or_id>`, `--priority N`. Resolves names to IDs, calls `orchestrator.create_run()` + `orchestrator.execute_run()`, prints run ID and final status. |
| E6.3 | Open | — | — | Implement `eval run-matrix` command — `--evaluation <name_or_id>`, `--targets <id,id,id>`, `--name "matrix name"`. Creates RunGroup + N runs, executes sequentially or in parallel per execution_mode. Prints group ID and per-run statuses. |
| E6.4 | Open | — | — | Implement `eval status` command — `--run-id N` (single run detail), `--active` (all non-terminal runs), `--recent N` (last N completed runs). Tabular output with run ID, evaluation, target, status, progress, duration. |
| E6.5 | Open | — | — | Implement `eval list` command — `--evaluations`, `--datasets`, `--scorers`, `--targets`, `--machines` flags (at least one required). Tabular output for each entity type with key fields. |
| E6.6 | Open | — | — | Implement `eval compare` command — `--runs <id,id>`, `--format json|csv|text`. Calls comparison_service, prints metric deltas and item-level diff summary. Default format: text. |
| E6.7 | Open | — | — | Implement `eval export` command — `--run <id>`, `--format json|csv|html`, `--output <path>`. Exports full run results to file. |
| E6.8 | Open | — | — | Implement `eval rescore` command — `--run <id>`, `--scorer-config <json_path>`. Loads new scorer config from JSON file, calls rescore endpoint logic, prints updated metrics. |
| E6.9 | Open | — | — | Implement `eval serve` command — `--host 0.0.0.0`, `--port 8080`. Starts uvicorn with the FastAPI app. Uses EvalSettings defaults. |
| E6.10 | Open | — | — | CLI smoke tests — test `eval run`, `eval status`, `eval compare`, `eval export` against a test database using Click's `CliRunner`. |

### Phase E6 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E6: CLI commands for eval run, status, compare, export, serve`

---

## Phase E7: UI Templates (Dashboard, Entity Pages, Run Pages)

**Goal:** Implement the server-rendered evaluation UI using Jinja2 templates. After this phase, users can browse evaluations, datasets, targets, machines, and runs through a web interface.

**Depends on:** E5 (API routes that the templates call or that serve data).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E7.1 | Open | — | — | Create `eval/ui/__init__.py`, `eval/ui/server.py` — mount Jinja2 template engine and static file serving on the FastAPI app. Define base template with sidebar navigation: Dashboard, Evaluations, Datasets, Scorers, Targets, Machines, Runs, Reports. |
| E7.2 | Open | — | — | Create `eval/ui/static/css/` — base stylesheet. Minimal, functional design. Tables, cards, status badges, progress bars, form styling. |
| E7.3 | Open | — | — | Create `eval/ui/static/js/` — lightweight JS for table sorting, filter forms, auto-refresh (polling), diff highlighting, and multi-select for comparisons. |
| E7.4 | Open | — | — | Implement `eval/ui/templates/base.html` — layout with nav sidebar, content area, flash messages. |
| E7.5 | Open | — | — | Implement dashboard page (`templates/evaluations/dashboard.html`) — active runs with progress bars, recent completions, failure alerts, machine utilization summary. Auto-refreshes via JS polling. |
| E7.6 | Open | — | — | Implement evaluation pages — `list.html` (table with name, version, dataset, scorer count, last run, tags; create/archive actions), `detail.html` (header, version history, "New Run" trigger form, recent runs), `create.html` (form for new evaluation). |
| E7.7 | Open | — | — | Implement dataset pages — `list.html` (name, version count, latest item count, source, tags), `detail.html` (version list, item preview table with pagination). |
| E7.8 | Open | — | — | Implement target pages — `list.html` (name, model, provider, machine, runtime, key params; multi-select for diff), `detail.html` (full config display, clone button, run history). |
| E7.9 | Open | — | — | Implement run pages — `list.html` (table with filters for status/evaluation/target/machine/date/model; checkbox select → "Compare Selected"), `detail.html` (status badge, summary cards, tabs for Results/Scorer Breakdown/Configuration/Artifacts/Traces; item rows expand to full detail), `live.html` (auto-refresh variant with progress bar and streaming item table). |

### Phase E7 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E7: UI templates for dashboard, entity pages, and run views`

---

## Phase E8: Comparison UI, Reports, and Saved Presets

**Goal:** Implement the side-by-side comparison view, report builder, and preset system. After this phase, users can visually compare runs and generate exportable reports.

**Depends on:** E5, E7 (API comparison endpoints, base UI templates).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E8.1 | Open | — | — | Implement `templates/comparisons/compare.html` — multi-column layout (one column per run). Section 1: aggregate metric table with delta columns and win/loss color coding. Section 2: per-scorer pass rate and avg score side by side. |
| E8.2 | Open | — | — | Add item comparison section to compare.html — aligned table showing each item's output and scores across runs. Diff highlighting for output text (insertions green, deletions red). Filters: show only disagreements, only failures, only items above latency threshold. |
| E8.3 | Open | — | — | Add config diff section to compare.html — side-by-side target configuration with differing fields highlighted. Uses comparison_service.diff_target_configs(). |
| E8.4 | Open | — | — | Implement `templates/reports/dashboard.html` — preset report list (Best Coding Runs, Quantization Comparison, Standard Laptop Viability, Older Hardware Baseline). Custom report builder form: group_by, filters, metrics, date range. |
| E8.5 | Open | — | — | Add charts to report dashboard — bar chart (pass rate by model), scatter plot (quality vs latency), trend line (metrics over time). Use a lightweight JS charting library (Chart.js or similar). |
| E8.6 | Open | — | — | Implement report export — JSON, CSV, HTML download buttons. Generate via report_service and serve as file downloads. |
| E8.7 | Open | — | — | Implement saved preset CRUD in UI — create, edit, delete presets. Run a preset from the reports page. |

### Phase E8 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E8: Comparison UI, report builder, charts, and saved presets`

---

## Phase E9: Integration Tests, End-to-End Smoke Tests, and Documentation

**Goal:** Verify all acceptance criteria from the PDR. Run full end-to-end workflows. Update project documentation. After this phase, the evaluation pipeline is complete and verified.

**Depends on:** All prior phases (E1–E8).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| E9.1 | Open | — | — | End-to-end smoke test — create evaluation + dataset (with 5+ items) + scorer + target + machine → trigger run via API → poll until completion → verify item results + aggregate metrics → trigger second run with different target → compare both runs. Covers AC-1, AC-2. |
| E9.2 | Open | — | — | Historical inspectability test — complete a run, then query it by ID. Verify response contains full evaluation version, dataset version, scorer versions, target config snapshot, and machine snapshot. Covers AC-3. |
| E9.3 | Open | — | — | CLI smoke test — `eval run`, `eval status`, `eval compare`, `eval export` against test database. Verify each command produces expected output and exit codes. Covers AC-4. |
| E9.4 | Open | — | — | Machine class filter test — create runs on different hardware classes, query `GET /runs?hardware_class=standard_laptop`, verify only matching runs returned. Covers AC-5. |
| E9.5 | Open | — | — | Active vs historical separation test — create active (queued/running) and completed runs. Verify dashboard API returns them in distinct groups. Covers AC-6. |
| E9.6 | Open | — | — | Rescore test — complete a run with one scorer, then `POST /runs/{id}/rescore` with a different scorer config. Verify new scores are computed on stored outputs without re-running generation. Verify original outputs are unchanged. Covers AC-7. |
| E9.7 | Open | — | — | Partial failure test — create a run where 1 of 10 items fails (via a bad prompt or endpoint error). Verify status=partially_completed, 9 items have results, 1 has error captured. Covers AC-8. |
| E9.8 | Open | — | — | Update `README.md` — add eval pipeline section: purpose, quick start (eval serve, eval run), architecture overview, API reference link. Update `CLAUDE.md` — add eval build/test commands, eval package structure, key patterns (adapters, scorers, orchestrator). |
| E9.9 | Open | — | — | Create `tests/test_eval/fixtures/` — `sample_dataset.json` (5 coding + 5 general items), `sample_scorer.py` (custom scorer example), `sample_target.json` (local ollama config). Used by integration tests and as user examples. |

### Phase E9 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Eval Phase E9: Integration tests, acceptance criteria verification, and documentation`
- **Final commit:** `Update README.md and CLAUDE.md with eval pipeline documentation`
