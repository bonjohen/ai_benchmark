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
|  12 | Open   |               |                 | Design the persistence model for EvaluationDefinition, EvaluationVersion, Dataset, DatasetVersion, TestCase, Scorer, ScorerVersion, TargetConfiguration, RunnerProfile, MachineProfile, Run, RunGroup, RunItemResult, RunAggregateMetric, Artifact, TraceReference, and Annotation. |
|  13 | Open   |               |                 | Implement schema definitions or ORM-free persistence structures for all core entities.                                                                                                                                                                                              |
|  14 | Open   |               |                 | Implement immutable versioning behavior for evaluation definitions, scorer versions, and dataset versions.                                                                                                                                                                          |
|  15 | Open   |               |                 | Implement storage for requested configuration values and effective execution values.                                                                                                                                                                                                |
|  16 | Open   |               |                 | Implement run-group support for matrix and scheduled grouped execution.                                                                                                                                                                                                             |
|  17 | Open   |               |                 | Implement storage for tags, notes, and annotations without overwriting immutable execution facts.                                                                                                                                                                                   |
|  18 | Open   |               |                 | Add migration or schema-bootstrap logic for a clean local database initialization.                                                                                                                                                                                                  |
|  19 | Open   |               |                 | Add repository-level tests for create, read, update, archive, and immutable version behavior.                                                                                                                                                                                       |
|  20 | Open   |               |                 | Update readme.md with the current data model, storage approach, and Phase 2 progress.                                                                                                                                                                                               |
|  21 | Open   |               |                 | Stage all Phase 2 changes.                                                                                                                                                                                                                                                          |
|  22 | Open   |               |                 | Commit all Phase 2 changes with a phase-complete commit message.                                                                                                                                                                                                                    |
|  23 | Open   |               |                 | Immediately begin Phase 3.                                                                                                                                                                                                                                                          |

## Phase 3 — Runner and Machine Registry

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  24 | Open   |               |                 | Implement RunnerProfile support for Ollama, LM Studio, llama.cpp, MLX or MLX-LM, vLLM, SGLang, TensorRT-LLM, and OpenVINO GenAI.                                                                     |
|  25 | Open   |               |                 | Define runner metadata fields including runner class, version, supported machine classes, supported model families, parameter surface, and notes.                                                    |
|  26 | Open   |               |                 | Implement MachineProfile support for DGX Spark, Apple Silicon MacBook Pro M4 64G, Apple Silicon Mac mini 24G, RTX 4070 desktop, ASUS Vivobook S 15, GTX 1060 6G laptop, and Raspberry Pi edge class. |
|  27 | Open   |               |                 | Define machine metadata fields including hardware class, CPU, GPU or accelerator, RAM, storage summary, runtime stack, availability, and health state.                                               |
|  28 | Open   |               |                 | Implement compatibility rules between runner profiles and machine classes.                                                                                                                           |
|  29 | Open   |               |                 | Implement machine snapshot capture to persist the exact runtime context used at run time.                                                                                                            |
|  30 | Open   |               |                 | Implement requested-machine versus actual-machine recording.                                                                                                                                         |
|  31 | Open   |               |                 | Seed initial runner and machine records for the known lab environments.                                                                                                                              |
|  32 | Open   |               |                 | Update readme.md with runner coverage, machine coverage, and Phase 3 progress.                                                                                                                       |
|  33 | Open   |               |                 | Stage all Phase 3 changes.                                                                                                                                                                           |
|  34 | Open   |               |                 | Commit all Phase 3 changes with a phase-complete commit message.                                                                                                                                     |
|  35 | Open   |               |                 | Immediately begin Phase 4.                                                                                                                                                                           |

## Phase 4 — Evaluation Definitions, Datasets, and Scorers

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                    |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  36 | Open   |               |                 | Implement CRUD operations for evaluation definitions and versions.                                                                                                             |
|  37 | Open   |               |                 | Implement dataset creation, import, versioning, and snapshotting.                                                                                                              |
|  38 | Open   |               |                 | Implement test-case tagging, filtering, and subset generation for smoke tests and focused test sets.                                                                           |
|  39 | Open   |               |                 | Implement scorer definitions for exact match, fuzzy match, rubric scoring, format validation, structured-output validation, latency scoring, cost scoring, and safety scoring. |
|  40 | Open   |               |                 | Implement evaluator-model scorer definitions with model identity, rubric, and parameter capture.                                                                               |
|  41 | Open   |               |                 | Implement scorer versioning and scorer-set assignment to evaluation definitions.                                                                                               |
|  42 | Open   |               |                 | Implement dataset preview and validation logic for evaluation binding.                                                                                                         |
|  43 | Open   |               |                 | Implement validation rules so a run cannot start with missing dataset, scorer, or incompatible schema.                                                                         |
|  44 | Open   |               |                 | Add test coverage for evaluation versioning, dataset snapshotting, and scorer versioning behavior.                                                                             |
|  45 | Open   |               |                 | Update readme.md with evaluation, dataset, and scorer capabilities delivered in Phase 4.                                                                                       |
|  46 | Open   |               |                 | Stage all Phase 4 changes.                                                                                                                                                     |
|  47 | Open   |               |                 | Commit all Phase 4 changes with a phase-complete commit message.                                                                                                               |
|  48 | Open   |               |                 | Immediately begin Phase 5.                                                                                                                                                     |

## Phase 5 — Target Configurations and Execution Matrix

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                            |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  49 | Open   |               |                 | Implement target configuration CRUD operations.                                                                                                                                                        |
|  50 | Open   |               |                 | Support target configuration fields for machine, runner, model, endpoint, runtime backend, prompt wrapper, inference parameters, context settings, quantization, GPU layer count, batching, and notes. |
|  51 | Open   |               |                 | Implement target configuration cloning for one-variable-at-a-time comparisons.                                                                                                                         |
|  52 | Open   |               |                 | Implement compatibility validation between target configuration, runner, model family, and machine class.                                                                                              |
|  53 | Open   |               |                 | Implement tagging for target configurations such as baseline, Apple-native, NVIDIA-optimized, Intel-NPU, standard-laptop, old-gpu, and edge.                                                           |
|  54 | Open   |               |                 | Implement matrix expansion logic to turn one evaluation plus many target configurations into a run group with child runs.                                                                              |
|  55 | Open   |               |                 | Implement persistence for requested configuration and effective configuration after runner startup.                                                                                                    |
|  56 | Open   |               |                 | Add automated tests for target cloning, compatibility validation, and matrix expansion.                                                                                                                |
|  57 | Open   |               |                 | Update readme.md with target configuration and execution-matrix behavior delivered in Phase 5.                                                                                                         |
|  58 | Open   |               |                 | Stage all Phase 5 changes.                                                                                                                                                                             |
|  59 | Open   |               |                 | Commit all Phase 5 changes with a phase-complete commit message.                                                                                                                                       |
|  60 | Open   |               |                 | Immediately begin Phase 6.                                                                                                                                                                             |

## Phase 6 — Execution Engine and Scheduler

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                                                                |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|  61 | Open   |               |                 | Implement run lifecycle state handling for queued, validating, preparing, running generation, running scorers, aggregating, completed, partially completed, failed, blocked, and canceled. |
|  62 | Open   |               |                 | Implement the scheduler for manual, scheduled, batch, and matrix execution.                                                                                                                |
|  63 | Open   |               |                 | Implement machine-aware dispatch and runner-aware dispatch.                                                                                                                                |
|  64 | Open   |               |                 | Implement concurrency limits, queue priorities, and machine reservation logic.                                                                                                             |
|  65 | Open   |               |                 | Implement local-only, machine allow-list, runner allow-list, cost cap, and time cap restrictions.                                                                                          |
|  66 | Open   |               |                 | Implement retry and resume logic for failed items, failed scorers, and interrupted runs.                                                                                                   |
|  67 | Open   |               |                 | Implement run progress tracking at both run and run-group level.                                                                                                                           |
|  68 | Open   |               |                 | Implement scheduler event logging for queue decisions and execution transitions.                                                                                                           |
|  69 | Open   |               |                 | Add test coverage for queueing, scheduling, retry, resume, and constraint enforcement.                                                                                                     |
|  70 | Open   |               |                 | Update readme.md with scheduler behavior and Phase 6 progress.                                                                                                                             |
|  71 | Open   |               |                 | Stage all Phase 6 changes.                                                                                                                                                                 |
|  72 | Open   |               |                 | Commit all Phase 6 changes with a phase-complete commit message.                                                                                                                           |
|  73 | Open   |               |                 | Immediately begin Phase 7.                                                                                                                                                                 |

## Phase 7 — Runner Adapters and Execution Integrations

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                           |
| --: | ------ | ------------- | --------------- | --------------------------------------------------------------------------------------------------------------------- |
|  74 | Open   |               |                 | Implement a runner adapter interface for model invocation, health check, capability inspection, and metadata capture. |
|  75 | Open   |               |                 | Implement the Ollama adapter.                                                                                         |
|  76 | Open   |               |                 | Implement the LM Studio adapter.                                                                                      |
|  77 | Open   |               |                 | Implement the llama.cpp adapter.                                                                                      |
|  78 | Open   |               |                 | Implement the MLX or MLX-LM adapter.                                                                                  |
|  79 | Open   |               |                 | Implement the vLLM adapter.                                                                                           |
|  80 | Open   |               |                 | Implement the SGLang adapter.                                                                                         |
|  81 | Open   |               |                 | Implement the TensorRT-LLM adapter.                                                                                   |
|  82 | Open   |               |                 | Implement the OpenVINO GenAI adapter.                                                                                 |
|  83 | Open   |               |                 | Implement normalized response capture so all runners feed a common evaluation result format.                          |
|  84 | Open   |               |                 | Implement runner-version and effective-runtime capture at execution time.                                             |
|  85 | Open   |               |                 | Add adapter tests and compatibility tests for supported runner classes.                                               |
|  86 | Open   |               |                 | Update readme.md with runner adapter coverage and Phase 7 progress.                                                   |
|  87 | Open   |               |                 | Stage all Phase 7 changes.                                                                                            |
|  88 | Open   |               |                 | Commit all Phase 7 changes with a phase-complete commit message.                                                      |
|  89 | Open   |               |                 | Immediately begin Phase 8.                                                                                            |

## Phase 8 — Result Capture, Traces, Artifacts, and Rescoring

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                            |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------- |
|  90 | Open   |               |                 | Implement storage of raw outputs, normalized outputs, scorer outputs, and aggregate metrics.                           |
|  91 | Open   |               |                 | Implement trace references, token usage, latency breakdowns, retry counts, and cost estimates where available.         |
|  92 | Open   |               |                 | Implement execution log storage separate from evaluation artifact storage.                                             |
|  93 | Open   |               |                 | Implement artifact generation for JSON exports, CSV summaries, markdown reports, HTML reports, and comparison bundles. |
|  94 | Open   |               |                 | Implement artifact retention policy support.                                                                           |
|  95 | Open   |               |                 | Implement rescoring of stored outputs without regeneration when possible.                                              |
|  96 | Open   |               |                 | Implement re-aggregation of run metrics after rescoring.                                                               |
|  97 | Open   |               |                 | Add tests for trace capture, artifact generation, and rescoring correctness.                                           |
|  98 | Open   |               |                 | Update readme.md with result-capture and artifact capabilities delivered in Phase 8.                                   |
|  99 | Open   |               |                 | Stage all Phase 8 changes.                                                                                             |
| 100 | Open   |               |                 | Commit all Phase 8 changes with a phase-complete commit message.                                                       |
| 101 | Open   |               |                 | Immediately begin Phase 9.                                                                                             |

## Phase 9 — API and CLI for Automation

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                          |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 102 | Open   |               |                 | Implement API endpoints for evaluations, datasets, scorers, target configurations, runners, machines, runs, run groups, and reports. |
| 103 | Open   |               |                 | Implement API endpoints for run launch, run resume, scorer retry, item retry, and cancellation.                                      |
| 104 | Open   |               |                 | Implement CLI commands for run launch, run status, run compare, report export, and machine or runner inspection.                     |
| 105 | Open   |               |                 | Implement machine-readable run launch input suitable for invocation from a Claude Code skill.                                        |
| 106 | Open   |               |                 | Implement authentication or local authorization appropriate for lab use.                                                             |
| 107 | Open   |               |                 | Add API and CLI tests covering normal and failure paths.                                                                             |
| 108 | Open   |               |                 | Produce example automation payloads for scheduled evaluation execution.                                                              |
| 109 | Open   |               |                 | Update readme.md with API and CLI usage delivered in Phase 9.                                                                        |
| 110 | Open   |               |                 | Stage all Phase 9 changes.                                                                                                           |
| 111 | Open   |               |                 | Commit all Phase 9 changes with a phase-complete commit message.                                                                     |
| 112 | Open   |               |                 | Immediately begin Phase 10.                                                                                                          |

## Phase 10 — Frontend Foundation and Navigation

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 113 | Open   |               |                 | Implement the frontend application shell and routing.                                                                                                |
| 114 | Open   |               |                 | Implement top-level navigation for Evaluations, Datasets, Scorers, Target Configurations, Runs, Run Groups, Machines, Runners, and Reports.          |
| 115 | Open   |               |                 | Implement current activity and historical activity separation in the UI.                                                                             |
| 116 | Open   |               |                 | Implement shared filter state, saved views, and global search across primary entities.                                                               |
| 117 | Open   |               |                 | Implement a reusable metadata panel to show evaluation version, dataset version, scorer versions, runner, machine, and target configuration context. |
| 118 | Open   |               |                 | Implement foundational loading, error, empty, and blocked-state handling across the UI.                                                              |
| 119 | Open   |               |                 | Add frontend tests for navigation, search, and saved-view behavior.                                                                                  |
| 120 | Open   |               |                 | Update readme.md with frontend foundation and Phase 10 progress.                                                                                     |
| 121 | Open   |               |                 | Stage all Phase 10 changes.                                                                                                                          |
| 122 | Open   |               |                 | Commit all Phase 10 changes with a phase-complete commit message.                                                                                    |
| 123 | Open   |               |                 | Immediately begin Phase 11.                                                                                                                          |

## Phase 11 — Definition Management UI

| No. | Status | Started (PST) | Completed (PST) | Description                                                                           |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------- |
| 124 | Open   |               |                 | Implement the evaluation definition list and detail pages.                            |
| 125 | Open   |               |                 | Implement evaluation create, edit, clone, archive, and version workflows.             |
| 126 | Open   |               |                 | Implement dataset list, detail, preview, and subset views.                            |
| 127 | Open   |               |                 | Implement scorer list, detail, version history, and scorer-set assignment views.      |
| 128 | Open   |               |                 | Implement target configuration list, detail, edit, clone, and compare views.          |
| 129 | Open   |               |                 | Implement runner inventory and runner detail pages.                                   |
| 130 | Open   |               |                 | Implement machine inventory and machine detail pages.                                 |
| 131 | Open   |               |                 | Add UI tests for evaluation, dataset, scorer, target, runner, and machine management. |
| 132 | Open   |               |                 | Update readme.md with definition-management UI delivered in Phase 11.                 |
| 133 | Open   |               |                 | Stage all Phase 11 changes.                                                           |
| 134 | Open   |               |                 | Commit all Phase 11 changes with a phase-complete commit message.                     |
| 135 | Open   |               |                 | Immediately begin Phase 12.                                                           |

## Phase 12 — Run Launch and Live Monitoring UI

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                               |
| --: | ------ | ------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 136 | Open   |               |                 | Implement the run-launch screen for single-run and matrix-run execution.                                                                  |
| 137 | Open   |               |                 | Implement launch presets for smoke test, full benchmark, regression check, runner comparison, machine comparison, and rerun failed items. |
| 138 | Open   |               |                 | Implement validation warnings for incompatible machine, runner, model, or cost settings.                                                  |
| 139 | Open   |               |                 | Implement the live run list.                                                                                                              |
| 140 | Open   |               |                 | Implement the live run detail page with partial results, current stage, failures, and timing.                                             |
| 141 | Open   |               |                 | Implement live run-group monitoring for matrix jobs.                                                                                      |
| 142 | Open   |               |                 | Implement cancel, retry, and resume actions where supported.                                                                              |
| 143 | Open   |               |                 | Add UI tests for launch workflows and live monitoring.                                                                                    |
| 144 | Open   |               |                 | Update readme.md with run-launch and live-monitoring UI delivered in Phase 12.                                                            |
| 145 | Open   |               |                 | Stage all Phase 12 changes.                                                                                                               |
| 146 | Open   |               |                 | Commit all Phase 12 changes with a phase-complete commit message.                                                                         |
| 147 | Open   |               |                 | Immediately begin Phase 13.                                                                                                               |

## Phase 13 — Historical Review, Comparison, and Reporting

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                       |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 148 | Open   |               |                 | Implement the historical run list with filtering by evaluation, model, runner, machine, machine class, scorer, dataset version, date, and status. |
| 149 | Open   |               |                 | Implement the historical run detail page with outputs, metrics, traces, artifacts, and annotations.                                               |
| 150 | Open   |               |                 | Implement side-by-side comparison for at least two runs.                                                                                          |
| 151 | Open   |               |                 | Implement comparison filters for only failures, only disagreements, only changed outcomes, and only regressions.                                  |
| 152 | Open   |               |                 | Implement report generation by evaluation suite, runner, machine class, model family, and date range.                                             |
| 153 | Open   |               |                 | Implement saved report presets and export flows for JSON, CSV, markdown, and HTML.                                                                |
| 154 | Open   |               |                 | Add UI and backend tests for historical review, comparison, and reporting.                                                                        |
| 155 | Open   |               |                 | Update readme.md with historical review and reporting delivered in Phase 13.                                                                      |
| 156 | Open   |               |                 | Stage all Phase 13 changes.                                                                                                                       |
| 157 | Open   |               |                 | Commit all Phase 13 changes with a phase-complete commit message.                                                                                 |
| 158 | Open   |               |                 | Immediately begin Phase 14.                                                                                                                       |

## Phase 14 — Privacy, Hardening, and Release Readiness

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                     |
| --: | ------ | ------------- | --------------- | --------------------------------------------------------------------------------------------------------------- |
| 159 | Open   |               |                 | Implement local-only enforcement so protected datasets and runs cannot be sent to remote providers.             |
| 160 | Open   |               |                 | Implement audit trails for what data was sent to which runner or endpoint.                                      |
| 161 | Open   |               |                 | Implement retention controls for traces, raw outputs, and logs.                                                 |
| 162 | Open   |               |                 | Run end-to-end validation across DGX Spark, Apple Silicon, RTX 4070, and Vivobook-class targets where possible. |
| 163 | Open   |               |                 | Run regression tests across core workflows: define, launch, monitor, review, compare, and export.               |
| 164 | Open   |               |                 | Fix release-blocking defects and update statuses to Blocked where external dependencies prevent completion.     |
| 165 | Open   |               |                 | Prepare release notes for the phased initial release.                                                           |
| 166 | Open   |               |                 | Update readme.md with final release status, feature coverage, known limitations, and next steps.                |
| 167 | Open   |               |                 | Stage all Phase 14 changes.                                                                                     |
| 168 | Open   |               |                 | Commit all Phase 14 changes with a phase-complete commit message.                                               |
| 169 | Open   |               |                 | Immediately proceed to the next phase of post-release backlog planning.                                         |

## Operating Rules for Execution

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                       |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 170 | Open   |               |                 | At the end of every phase, update readme.md to reflect what was delivered, what remains, and any known limitations.                               |
| 171 | Open   |               |                 | At the end of every phase, stage all changes created during that phase.                                                                           |
| 172 | Open   |               |                 | At the end of every phase, create a commit with a clear phase-complete commit message.                                                            |
| 173 | Open   |               |                 | After committing a phase, immediately begin the next phase unless a task is explicitly marked Blocked.                                            |
| 174 | Open   |               |                 | If a task becomes Blocked, record the blocking reason in the task description or linked implementation log before continuing with unblocked work. |
