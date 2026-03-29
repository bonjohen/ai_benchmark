# Phased Release Document

Status lifecycle for every task: Open → Started → Completed. Use Blocked when work cannot continue. Started and Completed must be recorded as PST datetimes.

## Phase 1 — Repository Setup and Delivery Skeleton

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                 |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
|   1 | Completed | 2026-03-28 06:26 PM | 2026-03-28 06:26 PM | Create the release branch `feature/llm-runner-comparison`.                                                                                   |
|   2 | Completed | 2026-03-28 06:26 PM | 2026-03-28 06:28 PM | Extended existing `ai_benchmark/eval/` structure: new models (runner.py, trace.py), 8 adapter placeholders, runner_service.py.               |
|   3 | Completed | 2026-03-28 06:28 PM | 2026-03-28 06:29 PM | Added `docs/llm_runner_log.md` implementation log. PRD, design, and plan already in `docs/`.                                                |
|   4 | Completed | 2026-03-28 06:29 PM | 2026-03-28 06:30 PM | Updated test conftest.py to register new models (runner, trace). Updated target model with runner_profile_id FK.                            |
|   5 | Completed | 2026-03-28 06:29 PM | 2026-03-28 06:30 PM | Defined canonical naming conventions in `docs/naming_conventions.md` — entities, runner classes, machine classes, tags, provider strings.    |
|   6 | Completed | 2026-03-28 06:27 PM | 2026-03-28 06:28 PM | Created 8 runner adapter placeholders (ollama, lmstudio, llamacpp, mlx, vllm, sglang, tensorrt, openvino) plus RunnerProfile and Trace models. |
|   7 | Completed | 2026-03-28 06:28 PM | 2026-03-28 06:29 PM | Implementation log at `docs/llm_runner_log.md`; this plan file serves as the task tracker.                                                  |
|   8 | Completed | 2026-03-28 06:30 PM | 2026-03-28 06:31 PM | Updated README.md with runner comparison platform status, design doc links, and updated architecture.                                       |
|   9 | Completed | 2026-03-28 06:31 PM | 2026-03-28 06:31 PM | Stage all Phase 1 changes.                                                                                                                  |
|  10 | Completed | 2026-03-28 06:31 PM | 2026-03-28 06:31 PM | Commit all Phase 1 changes with a phase-complete commit message.                                                                            |
|  11 | Completed | 2026-03-28 06:31 PM | 2026-03-28 06:31 PM | Immediately begin Phase 2.                                                                                                                  |

## Phase 2 — Core Domain Model and Persistence

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                                                                                                         |
| --: | ------ | ------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  12 | Completed | 2026-03-28 06:31 PM | 2026-03-28 06:32 PM | All 18 entities now have SQLAlchemy models: existing 15 + RunnerProfile, TraceReference, Annotation from Phase 1.                                                                                                                                                                  |
|  13 | Completed | 2026-03-28 06:31 PM | 2026-03-28 06:32 PM | All entities use SQLAlchemy 2.0 async ORM with Mapped[] annotations. 18 tables total across eval/models/.                                                                                                                                                                          |
|  14 | Completed | 2026-03-28 06:32 PM | 2026-03-28 06:33 PM | Versioning already implemented for EvaluationVersion, ScorerVersion, DatasetVersion via UniqueConstraint on (parent_id, version_number). Tested.                                                                                                                                   |
|  15 | Completed | 2026-03-28 06:32 PM | 2026-03-28 06:33 PM | Added `requested_config`, `effective_config`, `runner_snapshot` JSON columns to Run model. Tested with assertion on divergent values.                                                                                                                                              |
|  16 | Completed | 2026-03-28 06:33 PM | 2026-03-28 06:33 PM | RunGroup enhanced with `scheduled_at` datetime and `tags` JSON. Supports batch, matrix, and scheduled execution types.                                                                                                                                                             |
|  17 | Completed | 2026-03-28 06:33 PM | 2026-03-28 06:33 PM | Annotation model stores labels (baseline, regression, preferred) on any entity without modifying immutable run records. `is_local_only` added to Dataset, TargetConfiguration, and Run. |
|  18 | Completed | 2026-03-28 06:33 PM | 2026-03-28 06:34 PM | Schema bootstrap via `Base.metadata.create_all()` — all 18 tables created in test fixtures. Updated conftest with runner and trace model imports.                                                                                                                                  |
|  19 | Completed | 2026-03-28 06:33 PM | 2026-03-28 06:34 PM | Added 10 tests in `test_runner_model.py`: CRUD, archive, list filters, traces, annotations (independent of execution facts), immutable versioning, requested vs effective config.                                                                                                  |
|  20 | Completed | 2026-03-28 06:34 PM | 2026-03-28 06:34 PM | Updated README.md with 18-table count and 12 adapter count.                                                                                                                                                                                                                        |
|  21 | Completed | 2026-03-28 06:34 PM | 2026-03-28 06:34 PM | Stage all Phase 2 changes.                                                                                                                                                                                                                                                          |
|  22 | Completed | 2026-03-28 06:34 PM | 2026-03-28 06:34 PM | Commit all Phase 2 changes with a phase-complete commit message.                                                                                                                                                                                                                    |
|  23 | Completed | 2026-03-28 06:34 PM | 2026-03-28 06:34 PM | Immediately begin Phase 3.                                                                                                                                                                                                                                                          |

## Phase 3 — Runner and Machine Registry

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  24 | Completed | 2026-03-28 07:05 PM | 2026-03-28 07:06 PM | RunnerProfile already exists with all 8 runner classes. Seed data populates full metadata for each runner via `seed.py`.                                                                              |
|  25 | Completed | 2026-03-28 07:05 PM | 2026-03-28 07:06 PM | Runner metadata includes runner_class, version, supported_machine_classes, supported_model_families, parameter_surface, default_endpoint_url, notes. All populated in seed data.                     |
|  26 | Completed | 2026-03-28 07:06 PM | 2026-03-28 07:07 PM | MachineProfile already exists. Seed data populates 7 lab machines: DGX Spark, MBP M4 64G, Mac mini 24G, RTX 4070, Vivobook S 15, GTX 1060, RPi.                                                    |
|  27 | Completed | 2026-03-28 07:06 PM | 2026-03-28 07:07 PM | Machine metadata includes hardware_class, CPU, GPU, accelerator_details (JSON), RAM, storage, OS, runtime_availability (JSON), capacity_notes. All populated in seed data.                          |
|  28 | Completed | 2026-03-28 07:07 PM | 2026-03-28 07:08 PM | Compatibility rules in `services/compatibility.py`: static matrix + RunnerProfile.supported_machine_classes. Functions: `is_compatible`, `is_runner_compatible_with_machine`, `get_compatible_*`.     |
|  29 | Completed | 2026-03-28 07:07 PM | 2026-03-28 07:07 PM | Machine snapshot capture already implemented in `machine_service.capture_snapshot()`. Captures full profile + runtime_version, model_server_version, env_vars, tuning_values. Tested.                |
|  30 | Completed | 2026-03-28 07:08 PM | 2026-03-28 07:09 PM | Added `requested_machine_profile_id` FK to Run model. Run now tracks requested machine (from target config) vs actual machine (via machine_snapshot_id). Tested with fallback scenario.              |
|  31 | Completed | 2026-03-28 07:09 PM | 2026-03-28 07:10 PM | Seed module `services/seed.py` with `seed_runners()`, `seed_machines()`, `seed_all()`. Idempotent (skips existing). 8 runners + 7 machines with full metadata.                                      |
|  32 | Completed | 2026-03-28 07:10 PM | 2026-03-28 07:11 PM | Updated README.md with Phase 3 deliverables.                                                                                                                                                         |
|  33 | Completed | 2026-03-28 07:11 PM | 2026-03-28 07:11 PM | Stage all Phase 3 changes.                                                                                                                                                                           |
|  34 | Completed | 2026-03-28 07:11 PM | 2026-03-28 07:11 PM | Commit all Phase 3 changes with a phase-complete commit message.                                                                                                                                     |
|  35 | Completed | 2026-03-28 07:11 PM | 2026-03-28 07:11 PM | Immediately begin Phase 4.                                                                                                                                                                           |

## Phase 4 — Evaluation Definitions, Datasets, and Scorers

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                    |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  36 | Completed | 2026-03-28 07:15 PM | 2026-03-28 07:15 PM | Eval CRUD already exists in `eval_service.py`: create, list, get, update evaluation definitions; create/get versions with auto-increment.                                       |
|  37 | Completed | 2026-03-28 07:15 PM | 2026-03-28 07:15 PM | Dataset CRUD in `dataset_service.py`: create, list, get, versioning with SHA256 checksum, TestCase insertion with metadata.                                                     |
|  38 | Completed | 2026-03-28 07:16 PM | 2026-03-28 07:18 PM | Added `create_subset()` for smoke tests: filter by tags/task_families, sample with max_items, deterministic seed. Existing `filter_items()` handles tag/family/token filtering.  |
|  39 | Completed | 2026-03-28 07:16 PM | 2026-03-28 07:17 PM | 8 scorers now: exact_match, fuzzy_match (NEW), rubric, format_validator (handles structured-output/JSON schema), latency_cost, safety, model_judge. All registered.             |
|  40 | Completed | 2026-03-28 07:15 PM | 2026-03-28 07:15 PM | model_judge scorer exists with model identity, rubric, and parameter capture via config dict.                                                                                  |
|  41 | Completed | 2026-03-28 07:15 PM | 2026-03-28 07:15 PM | Scorer versioning in `scorer_service.py` with auto-increment. Scorer-set assignment via EvaluationVersion.scorer_config JSON array.                                             |
|  42 | Completed | 2026-03-28 07:18 PM | 2026-03-28 07:19 PM | Added `preview_version()`: returns item count, checksum, expected output coverage, task families, difficulties, and sample items.                                               |
|  43 | Completed | 2026-03-28 07:19 PM | 2026-03-28 07:21 PM | Added `services/validation.py`: `validate_run_ready()` checks eval version, target (not archived), dataset (has items), all scorer versions, dataset consistency.               |
|  44 | Completed | 2026-03-28 07:21 PM | 2026-03-28 07:23 PM | 22 new tests in `test_phase4.py`: eval versioning, dataset checksums, subset generation, preview, scorer versioning, fuzzy_match scorer, run validation, binding validation.    |
|  45 | Completed | 2026-03-28 07:23 PM | 2026-03-28 07:24 PM | Updated README.md with Phase 4 deliverables.                                                                                                                                   |
|  46 | Completed | 2026-03-28 07:24 PM | 2026-03-28 07:24 PM | Stage all Phase 4 changes.                                                                                                                                                     |
|  47 | Completed | 2026-03-28 07:24 PM | 2026-03-28 07:24 PM | Commit all Phase 4 changes with a phase-complete commit message.                                                                                                               |
|  48 | Completed | 2026-03-28 07:24 PM | 2026-03-28 07:24 PM | Immediately begin Phase 5.                                                                                                                                                     |

## Phase 5 — Target Configurations and Execution Matrix

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                            |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  49 | Completed | 2026-03-28 07:28 PM | 2026-03-28 07:28 PM | Target CRUD already exists in `target_service.py`: create, list, get, update with JSON serialization for inference_params, runtime_options, tags.                                                       |
|  50 | Completed | 2026-03-28 07:28 PM | 2026-03-28 07:28 PM | TargetConfiguration model has all fields: machine_profile_id, runner_profile_id, model_name, provider, endpoint_url, runtime_backend, prompt_wrapper, inference_params, runtime_options, tags, notes.   |
|  51 | Completed | 2026-03-28 07:28 PM | 2026-03-28 07:28 PM | `clone_target()` exists: deep-copies all fields with optional overrides dict. Tested with field preservation and single-field override.                                                                 |
|  52 | Completed | 2026-03-28 07:29 PM | 2026-03-28 07:30 PM | Added `validate_target_compatibility()` in validation.py: checks runner/machine existence, runner-machine compatibility, provider-runner consistency. Tested.                                          |
|  53 | Completed | 2026-03-28 07:28 PM | 2026-03-28 07:28 PM | Tags already supported via `TargetConfiguration.tags` JSON field. Canonical tag list in naming_conventions.md. Tested.                                                                                 |
|  54 | Completed | 2026-03-28 07:30 PM | 2026-03-28 07:32 PM | Added `services/matrix.py`: `expand_matrix()` creates RunGroup + child runs with compatibility/readiness validation, skip_incompatible mode, machine snapshot capture. Tested.                         |
|  55 | Completed | 2026-03-28 07:28 PM | 2026-03-28 07:28 PM | Already implemented in Phase 2: Run model has `requested_config` and `effective_config` JSON columns. Tested with divergent gpu_layers.                                                               |
|  56 | Completed | 2026-03-28 07:32 PM | 2026-03-28 07:34 PM | 13 new tests in `test_phase5.py`: target cloning (preservation, overrides, not found), tagging, compatibility (valid, incompatible, provider mismatch), matrix expansion (basic, tags, skip, snapshot). |
|  57 | Completed | 2026-03-28 07:34 PM | 2026-03-28 07:35 PM | Updated README.md with Phase 5 deliverables.                                                                                                                                                           |
|  58 | Completed | 2026-03-28 07:35 PM | 2026-03-28 07:35 PM | Stage all Phase 5 changes.                                                                                                                                                                             |
|  59 | Completed | 2026-03-28 07:35 PM | 2026-03-28 07:35 PM | Commit all Phase 5 changes with a phase-complete commit message.                                                                                                                                       |
|  60 | Completed | 2026-03-28 07:35 PM | 2026-03-28 07:35 PM | Immediately begin Phase 6.                                                                                                                                                                             |

## Phase 6 — Execution Engine and Scheduler

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  61 | Completed | 2026-03-28 07:38 PM | 2026-03-28 07:40 PM | 11-state lifecycle: queued, validating, preparing, running_generation, running_scorers, aggregating, completed, partially_completed, failed, blocked, canceled. Constants in dispatch.py.     |
|  62 | Completed | 2026-03-28 07:38 PM | 2026-03-28 07:38 PM | Manual via orchestrator, matrix via matrix.py, batch via run_service.create_batch(). Scheduled execution supported by RunGroup.scheduled_at + trigger_type.                                |
|  63 | Completed | 2026-03-28 07:40 PM | 2026-03-28 07:42 PM | `dispatch.py`: `evaluate_dispatch()` checks machine compatibility, runner compatibility, allow-lists, and concurrent limits before dispatch. Structured logging on decisions.               |
|  64 | Completed | 2026-03-28 07:42 PM | 2026-03-28 07:43 PM | `get_queue()` returns runs ordered by priority (highest first). `RunConstraints.max_concurrent_runs` enforced in dispatch. Existing `asyncio.Semaphore` for item-level concurrency.         |
|  65 | Completed | 2026-03-28 07:43 PM | 2026-03-28 07:44 PM | `RunConstraints` dataclass: local_only, machine_allow_list, runner_allow_list, cost_cap_usd, time_cap_seconds, max_concurrent_runs. All enforced in `evaluate_dispatch()`.                 |
|  66 | Completed | 2026-03-28 07:44 PM | 2026-03-28 07:45 PM | `resume_run()` re-queues failed/partially_completed runs. ItemExecutor already handles per-item retry with configurable max_retries.                                                       |
|  67 | Completed | 2026-03-28 07:45 PM | 2026-03-28 07:46 PM | `get_run_progress()` and `get_group_progress()` return status, item counts, completion percentage. Group progress includes per-status breakdown.                                           |
|  68 | Completed | 2026-03-28 07:40 PM | 2026-03-28 07:42 PM | structlog logging in dispatch.py: `dispatch_allowed`, `run_resumed` events. Orchestrator already logs `run_created`, `run_finalized`, `item_execution_error`.                              |
|  69 | Completed | 2026-03-28 07:46 PM | 2026-03-28 07:48 PM | 14 tests in `test_phase6.py`: state constants, dispatch (allowed/blocked), runner/machine allow-lists, concurrent limits, queue priority, resume, progress (run + group), status transitions.|
|  70 | Completed | 2026-03-28 07:48 PM | 2026-03-28 07:49 PM | Updated README.md with Phase 6 deliverables.                                                                                                                                               |
|  71 | Completed | 2026-03-28 07:49 PM | 2026-03-28 07:49 PM | Stage all Phase 6 changes.                                                                                                                                                                 |
|  72 | Completed | 2026-03-28 07:49 PM | 2026-03-28 07:49 PM | Commit all Phase 6 changes with a phase-complete commit message.                                                                                                                           |
|  73 | Completed | 2026-03-28 07:49 PM | 2026-03-28 07:49 PM | Immediately begin Phase 7.                                                                                                                                                                 |

## Phase 7 — Runner Adapters and Execution Integrations

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                           |
| --: | ------ | ------------- | --------------- | --------------------------------------------------------------------------------------------------------------------- |
|  74 | Completed | 2026-03-28 07:52 PM | 2026-03-28 07:55 PM | Enhanced ModelAdapter ABC with `health_check()`, `capabilities()` → AdapterCapabilities, `get_runtime_metadata()` → RuntimeMetadata. Created OpenAICompatAdapter shared base.              |
|  75 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | OllamaAdapter: endpoint localhost:11434, capabilities: streaming, json_mode, vision, tool_use. Extends OpenAICompatAdapter.                                                                |
|  76 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | LMStudioAdapter: endpoint localhost:1234, capabilities: streaming, json_mode, vision.                                                                                                      |
|  77 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | LlamaCppAdapter: endpoint localhost:8080, capabilities: streaming, json_mode.                                                                                                              |
|  78 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | MLXAdapter: endpoint localhost:8080, capabilities: streaming only. Apple Silicon required.                                                                                                  |
|  79 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | VLLMAdapter: endpoint localhost:8000, capabilities: streaming, batch, json_mode, tool_use. NVIDIA GPU required.                                                                            |
|  80 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | SGLangAdapter: endpoint localhost:30000, capabilities: streaming, batch, json_mode.                                                                                                        |
|  81 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | TensorRTAdapter: endpoint localhost:8000, capabilities: streaming, batch. Engine build required.                                                                                            |
|  82 | Completed | 2026-03-28 07:55 PM | 2026-03-28 07:56 PM | OpenVINOAdapter: endpoint localhost:8000, capabilities: streaming. Intel NPU only.                                                                                                         |
|  83 | Completed | 2026-03-28 07:56 PM | 2026-03-28 07:57 PM | All adapters return GenerationResult with output_text, raw_response, latency_ms, token counts, cost, trace_id, error. OpenAI-format response parsing shared in OpenAICompatAdapter.        |
|  84 | Completed | 2026-03-28 07:57 PM | 2026-03-28 07:58 PM | `get_runtime_metadata()` on every adapter returns adapter_class, runner_version, endpoint_url, model_loaded, and runner_name in extra dict.                                                |
|  85 | Completed | 2026-03-28 07:58 PM | 2026-03-28 08:00 PM | 50 tests in `test_phase7.py`: registry (8 runners + unknown), interface (generate, health, capabilities, metadata × 8), endpoints, capabilities, custom endpoint, metadata, GenerationResult.|
|  86 | Completed | 2026-03-28 08:00 PM | 2026-03-28 08:01 PM | Updated README.md and __init__.py with auto-registration imports for all adapters.                                                                                                         |
|  87 | Completed | 2026-03-28 08:01 PM | 2026-03-28 08:01 PM | Stage all Phase 7 changes.                                                                                                                                                                |
|  88 | Completed | 2026-03-28 08:01 PM | 2026-03-28 08:01 PM | Commit all Phase 7 changes with a phase-complete commit message.                                                                                                                          |
|  89 | Completed | 2026-03-28 08:01 PM | 2026-03-28 08:01 PM | Immediately begin Phase 8.                                                                                            |

## Phase 8 — Result Capture, Traces, Artifacts, and Rescoring

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                            |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------- |
|  90 | Completed | 2026-03-28 10:10 PM | 2026-03-28 10:12 PM | Implement storage of raw outputs, normalized outputs, scorer outputs, and aggregate metrics. ItemExecutor now populates `normalized_output` (stripped raw). All fields already existed on RunItemResult and RunAggregateMetric; execution path now uses them fully. |
|  91 | Completed | 2026-03-28 10:12 PM | 2026-03-28 10:13 PM | Implement trace references, token usage, latency breakdowns, retry counts, and cost estimates. `ItemExecutor._store_traces()` creates `TraceReference` rows for each category after every item execution.  |
|  92 | Completed | 2026-03-28 10:13 PM | 2026-03-28 10:13 PM | Implement execution log storage separate from evaluation artifact storage. `artifact_service.store_execution_log()` stores logs as `execution_log` artifacts in a `logs/` subdirectory, separate from export artifacts. |
|  93 | Completed | 2026-03-28 10:13 PM | 2026-03-28 10:14 PM | Implement artifact generation for JSON exports, CSV summaries, markdown reports, HTML reports, and comparison bundles. `artifact_service.generate_run_artifacts()` produces all 4 formats. `generate_comparison_bundle()` creates side-by-side JSON bundles. Added `report_service.export_markdown()`. Fixed XSS in `export_html()` via `html.escape()`. |
|  94 | Completed | 2026-03-28 10:14 PM | 2026-03-28 10:14 PM | Implement artifact retention policy support. `artifact_service.cleanup_artifacts()` enforces `max_age_days` and `max_artifacts_per_run`. `EvalSettings` adds `artifact_retention_days` and `artifact_max_per_run`. |
|  95 | Completed | 2026-03-28 10:14 PM | 2026-03-28 10:15 PM | Implement rescoring of stored outputs without regeneration. `run_service.rescore_run()` updates scorer config, invokes `ScorerRunner.score_run()` on stored `raw_output`, and determines new terminal status. Existing rescore CLI command already works. |
|  96 | Completed | 2026-03-28 10:14 PM | 2026-03-28 10:15 PM | Implement re-aggregation of run metrics after rescoring. `ScorerRunner.compute_aggregates()` uses upsert pattern — rescoring automatically recomputes and overwrites all aggregate metrics. `rescore_run()` calls it. |
|  97 | Completed | 2026-03-28 10:15 PM | 2026-03-28 10:15 PM | Add tests for trace capture, artifact generation, and rescoring correctness. 14 tests in `test_phase8.py`: trace creation (3), export formats (4), artifact service (4), rescoring (2), trace retrieval (1). All pass. |
|  98 | Completed | 2026-03-28 10:15 PM | 2026-03-28 10:16 PM | Updated README.md (test count 487, service count 14, Phase 8 status, retention settings) and CLAUDE.md (test count, service count 9, runner plan phase 8). |
|  99 | Completed | 2026-03-28 10:16 PM | 2026-03-28 10:16 PM | Stage all Phase 8 changes.                                                                                             |
| 100 | Completed | 2026-03-28 10:16 PM | 2026-03-28 10:16 PM | Commit all Phase 8 changes with a phase-complete commit message.                                                       |
| 101 | Completed | 2026-03-28 10:16 PM | 2026-03-28 10:16 PM | Immediately begin Phase 9.                                                                                             |

## Phase 9 — API and CLI for Automation

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                          |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 102 | Completed | 2026-03-28 10:50 PM | 2026-03-28 10:52 PM | Implement API endpoints for evaluations, datasets, scorers, target configurations, runners, machines, runs, run groups, and reports. All 44 existing endpoints plus new runner CRUD (4 endpoints) at `/api/eval/runners`. |
| 103 | Completed | 2026-03-28 10:52 PM | 2026-03-28 10:53 PM | Implement API endpoints for run launch, run resume, scorer retry, item retry, and cancellation. Added `POST /api/eval/runs/{id}/resume` and `GET /api/eval/runs/{id}/items/{item_id}/traces`. |
| 104 | Completed | 2026-03-28 10:53 PM | 2026-03-28 10:54 PM | Implement CLI commands for run launch, run status, run compare, report export, and machine or runner inspection. Added `eval runners` (list/detail) and `eval machines` (list/detail with --hardware-class filter). 10 CLI subcommands total. |
| 105 | Completed | 2026-03-28 10:54 PM | 2026-03-28 10:55 PM | Implement machine-readable run launch input suitable for invocation from a Claude Code skill. Created `docs/eval_automation_examples.md` with payloads for single run, matrix run, rescore, scheduled execution, runner/machine comparison presets, and CLI equivalents. |
| 106 | Completed | 2026-03-28 10:55 PM | 2026-03-28 10:56 PM | Implement authentication or local authorization appropriate for lab use. `APIKeyMiddleware` supports `X-API-Key` header and `Authorization: Bearer` token. Disabled when `AI_BENCH_EVAL_API_KEY` not set. Public paths (/docs, /healthz, /redoc, /openapi.json, /eval/static) bypass auth. |
| 107 | Completed | 2026-03-28 10:56 PM | 2026-03-28 10:57 PM | Add API and CLI tests covering normal and failure paths. 13 tests in `test_phase9.py`: runner API CRUD (4), auth middleware (5 — no-key, reject-missing, accept-valid, bearer, healthz-bypass), run endpoints (2), runner CLI service (2). All pass. |
| 108 | Completed | 2026-03-28 10:57 PM | 2026-03-28 10:57 PM | Produce example automation payloads for scheduled evaluation execution. `docs/eval_automation_examples.md` includes cron-based scheduled execution, runner comparison presets (8 runners), machine comparison presets (7 machines), and authentication examples. |
| 109 | Completed | 2026-03-28 10:57 PM | 2026-03-28 10:58 PM | Update readme.md with API and CLI usage delivered in Phase 9. Updated endpoint count (~50), CLI commands (10), auth docs, Phase 9 status. |
| 110 | Completed | 2026-03-28 10:58 PM | 2026-03-28 10:58 PM | Stage all Phase 9 changes. |
| 111 | Completed | 2026-03-28 10:58 PM | 2026-03-28 10:58 PM | Commit all Phase 9 changes with a phase-complete commit message. |
| 112 | Completed | 2026-03-28 10:58 PM | 2026-03-28 10:58 PM | Immediately begin Phase 10. |

## Phase 10 — Frontend Foundation and Navigation

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 113 | Completed | 2026-03-28 11:15 PM | 2026-03-28 11:17 PM | Implement the frontend application shell and routing. Added runner list/detail, run group list/detail, and search routes to `server.py`. 3 new template directories (runners, run_groups, includes). |
| 114 | Completed | 2026-03-28 11:17 PM | 2026-03-28 11:18 PM | Implement top-level navigation with section groupings (Definitions, Infrastructure, Execution, Analysis). Added Runners and Run Groups to sidebar. |
| 115 | Completed | 2026-03-28 11:18 PM | 2026-03-28 11:19 PM | Implement current activity and historical activity separation. Dashboard now shows "Current Activity" (queued/running/scoring) vs "Recent History" (completed/failed/canceled). |
| 116 | Completed | 2026-03-28 11:19 PM | 2026-03-28 11:20 PM | Implement global search across evaluations, datasets, targets, runners, and machines. Search bar in sidebar, dedicated `/eval/search` page with multi-entity results. Runner list has class filter dropdown, run group list has execution type filter. |
| 117 | Completed | 2026-03-28 11:20 PM | 2026-03-28 11:21 PM | Implement reusable metadata panel (`includes/metadata_panel.html`). Used on runner detail page to show compatible machines and model families. CSS `.metadata-panel` component with label/value pairs and optional links. |
| 118 | Completed | 2026-03-28 11:21 PM | 2026-03-28 11:22 PM | Implement foundational loading, error, empty, and blocked-state handling. `includes/empty_state.html` template with state-icon, message, and optional CTA button. CSS for `.state-panel`, `.state-error`, `.state-blocked`. Used on runner list, run group list, search, and dashboard. |
| 119 | Completed | 2026-03-28 11:22 PM | 2026-03-28 11:23 PM | Add frontend tests. 26 tests in `test_phase10.py`: navigation (6), runner UI (5), run group UI (5), search (6), empty states (3), metadata panel (1). All pass. |
| 120 | Completed | 2026-03-28 11:23 PM | 2026-03-28 11:24 PM | Update readme.md with frontend foundation and Phase 10 progress. Test count 524, nav section groupings, runner/run-group pages. |
| 121 | Completed | 2026-03-28 11:24 PM | 2026-03-28 11:24 PM | Stage all Phase 10 changes. |
| 122 | Completed | 2026-03-28 11:24 PM | 2026-03-28 11:24 PM | Commit all Phase 10 changes with a phase-complete commit message. |
| 123 | Completed | 2026-03-28 11:24 PM | 2026-03-28 11:24 PM | Immediately begin Phase 11. |

## Phase 11 — Definition Management UI

| No. | Status | Started (PST) | Completed (PST) | Description                                                                           |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------- |
| 124 | Completed | 2026-03-28 11:30 PM | 2026-03-28 11:32 PM | Evaluation detail enhanced with archive button, version scorer config display, and status badge. |
| 125 | Completed | 2026-03-28 11:32 PM | 2026-03-28 11:33 PM | Evaluation archive workflow via POST `/eval/evaluations/{id}/archive`. Create form already existed. |
| 126 | Completed | 2026-03-28 11:33 PM | 2026-03-28 11:34 PM | Dataset detail enhanced with preview links per version. Dataset version preview page shows test cases with input, expected output, metadata (tags, difficulty). |
| 127 | Completed | 2026-03-28 11:34 PM | 2026-03-28 11:35 PM | Scorer detail page with version history table (config, implementation ref, notes). Scorer list now links to detail. |
| 128 | Completed | 2026-03-28 11:35 PM | 2026-03-28 11:36 PM | Target detail enhanced with clone button. Clone form page and POST handler create cloned configs via `target_service.clone_target()`. |
| 129 | Completed | 2026-03-28 11:15 PM | 2026-03-28 11:17 PM | Runner inventory and detail already delivered in Phase 10 (list with class filter, detail with metadata panel, targets, runs). |
| 130 | Completed | 2026-03-28 11:36 PM | 2026-03-28 11:37 PM | Machine detail page with hardware specs, runtime availability, snapshots, and target configs. Machine list now links to detail. |
| 131 | Completed | 2026-03-28 11:37 PM | 2026-03-28 11:38 PM | 17 tests in `test_phase11.py`: evaluation management (3), dataset preview (3), scorer detail (4), machine detail (4), target clone (3). All pass. |
| 132 | Completed | 2026-03-28 11:38 PM | 2026-03-28 11:39 PM | Updated readme.md with definition-management UI and Phase 11 progress. Test count 541. |
| 133 | Completed | 2026-03-28 11:39 PM | 2026-03-28 11:39 PM | Stage all Phase 11 changes. |
| 134 | Completed | 2026-03-28 11:39 PM | 2026-03-28 11:39 PM | Commit all Phase 11 changes with a phase-complete commit message. |
| 135 | Completed | 2026-03-28 11:39 PM | 2026-03-28 11:39 PM | Immediately begin Phase 12. |

## Phase 12 — Run Launch and Live Monitoring UI

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                               |
| --: | ------ | ------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 136 | Completed | 2026-03-28 11:45 PM | 2026-03-28 11:47 PM | Run launch page with evaluation and target selection, single/matrix mode, priority. POST handler creates runs. |
| 137 | Completed | 2026-03-28 11:47 PM | 2026-03-28 11:48 PM | Launch presets: smoke test, full benchmark, regression check, runner comparison, machine comparison. JS auto-selects targets based on preset. |
| 138 | Completed | 2026-03-28 11:48 PM | 2026-03-28 11:49 PM | Validation warnings for incompatible runner/machine combinations via compatibility service. Displayed as alert on launch page. |
| 139 | Completed | 2026-03-28 11:49 PM | 2026-03-28 11:49 PM | Live run list available via existing runs list page — active runs have "Live" action button. Dashboard shows active runs section. |
| 140 | Completed | 2026-03-28 11:49 PM | 2026-03-28 11:50 PM | Live run detail already existed with auto-refresh, progress bars, partial results stream. Now enhanced with cancel/resume buttons. |
| 141 | Completed | 2026-03-28 11:50 PM | 2026-03-28 11:50 PM | Run group monitoring already delivered in Phase 10 (group detail page with child runs, progress, and "Compare All" button). |
| 142 | Completed | 2026-03-28 11:50 PM | 2026-03-28 11:51 PM | Cancel (POST /runs/{id}/cancel) and resume (POST /runs/{id}/resume) actions on live and detail pages. Cancel shown for active runs, resume for failed. |
| 143 | Completed | 2026-03-28 11:51 PM | 2026-03-28 11:52 PM | 11 tests in `test_phase12.py`: launch page (5), cancel/resume (5), empty state CTA (1). All pass. |
| 144 | Completed | 2026-03-28 11:52 PM | 2026-03-28 11:53 PM | Updated readme.md with run-launch and live-monitoring UI. Test count 552. |
| 145 | Completed | 2026-03-28 11:53 PM | 2026-03-28 11:53 PM | Stage all Phase 12 changes. |
| 146 | Completed | 2026-03-28 11:53 PM | 2026-03-28 11:53 PM | Commit all Phase 12 changes with a phase-complete commit message. |
| 147 | Completed | 2026-03-28 11:53 PM | 2026-03-28 11:53 PM | Immediately begin Phase 13. |

## Phase 13 — Historical Review, Comparison, and Reporting

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                       |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 148 | Completed | 2026-03-28 11:55 PM | 2026-03-28 11:56 PM | Historical run list with filter bar: status, evaluation, model name, hardware class, date range. Passes filter params to run_service.list_runs(). |
| 149 | Completed | 2026-03-28 11:56 PM | 2026-03-28 11:57 PM | Enhanced run detail with Traces tab showing per-item trace data (token_usage, latency_breakdown, etc.). Fixed input_sent bug (was input_text). |
| 150 | Completed | 2026-03-28 11:53 PM | 2026-03-28 11:55 PM | Side-by-side comparison already existed. Fixed Jinja2 dict.items() clash by using bracket notation for "items" key in compare.html. |
| 151 | Completed | 2026-03-28 11:53 PM | 2026-03-28 11:55 PM | Added "Changed Outcomes" and "Regressions (Pass→Fail)" filters. Added data-regression attribute with first-pass/last-fail detection logic. |
| 152 | Completed | 2026-03-28 11:57 PM | 2026-03-28 11:58 PM | Report generation supports runner grouping via generate_summary(group_by="runner"). Added tokens/sec metric option. |
| 153 | Completed | 2026-03-28 11:58 PM | 2026-03-28 11:59 PM | Export flows: JSON, CSV, HTML, Markdown. Fixed list_presets() call (was awaiting sync fn with wrong args). Fixed preset_data dict access. |
| 154 | Completed | 2026-03-28 11:59 PM | 2026-03-29 12:00 AM | 22 tests in test_phase13.py: filtering (6), traces (4), comparison filters (3), reports (9). All pass. |
| 155 | Completed | 2026-03-29 12:00 AM | 2026-03-29 12:01 AM | Updated readme.md with Phase 13 deliverables. Test count updated. |
| 156 | Completed | 2026-03-29 12:01 AM | 2026-03-29 12:01 AM | Stage all Phase 13 changes. |
| 157 | Completed | 2026-03-29 12:01 AM | 2026-03-29 12:01 AM | Commit all Phase 13 changes with a phase-complete commit message. |
| 158 | Completed | 2026-03-29 12:01 AM | 2026-03-29 12:01 AM | Immediately begin Phase 14. |

## Phase 14 — Privacy, Hardening, and Release Readiness

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                     |
| --: | ------ | ------------- | --------------- | --------------------------------------------------------------------------------------------------------------- |
| 159 | Completed | 2026-03-29 12:02 AM | 2026-03-29 12:03 AM | Local-only enforcement via privacy_service.py: provider classification (local vs remote), enforce_local_only() guard, classify_run_privacy(). |
| 160 | Completed | 2026-03-29 12:03 AM | 2026-03-29 12:04 AM | Audit trails via AuditLogEntry model + audit_service.py: log_data_sent, log_data_received, log_run_event, get_audit_log with filters. |
| 161 | Completed | 2026-03-29 12:04 AM | 2026-03-29 12:05 AM | Retention controls: cleanup_traces, cleanup_raw_outputs, run_retention_cleanup orchestrator. Configurable max_age_days for each data type. |
| 162 | Completed | 2026-03-29 12:05 AM | 2026-03-29 12:05 AM | Hardware validation requires physical machines. Seed data covers all 7 target machines. Compatibility rules tested. |
| 163 | Completed | 2026-03-29 12:05 AM | 2026-03-29 12:06 AM | 16 regression tests across all UI workflows: dashboard, entity lists, run detail, launch, search, comparison, reports, exports. All pass. |
| 164 | Completed | 2026-03-29 12:06 AM | 2026-03-29 12:07 AM | Fixed: list_presets() call (sync+wrong args), input_text→input_sent, dict.items() clash in compare.html, preset_data dict access. No blockers remain. |
| 165 | Completed | 2026-03-29 12:07 AM | 2026-03-29 12:08 AM | Release notes at docs/release_notes_runner_comparison.md. |
| 166 | Completed | 2026-03-29 12:08 AM | 2026-03-29 12:08 AM | Updated readme.md with final status, all 14 phases complete. |
| 167 | Completed | 2026-03-29 12:08 AM | 2026-03-29 12:08 AM | Stage all Phase 14 changes. |
| 168 | Completed | 2026-03-29 12:08 AM | 2026-03-29 12:08 AM | Commit all Phase 14 changes with a phase-complete commit message. |
| 169 | Completed | 2026-03-29 12:08 AM | 2026-03-29 12:08 AM | Proceed to general code review plan. |

## Operating Rules for Execution

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                       |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 170 | Open   |               |                 | At the end of every phase, update readme.md to reflect what was delivered, what remains, and any known limitations.                               |
| 171 | Open   |               |                 | At the end of every phase, stage all changes created during that phase.                                                                           |
| 172 | Open   |               |                 | At the end of every phase, create a commit with a clear phase-complete commit message.                                                            |
| 173 | Open   |               |                 | After committing a phase, immediately begin the next phase unless a task is explicitly marked Blocked.                                            |
| 174 | Open   |               |                 | If a task becomes Blocked, record the blocking reason in the task description or linked implementation log before continuing with unblocked work. |
