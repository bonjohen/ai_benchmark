1.01 | Open |  |  | Create the release branch for the evaluation pipeline and runner comparison platform.
1.02 | Open |  |  | Create the top-level project structure for backend, frontend, shared schemas, docs, and scripts.
1.03 | Open |  |  | Add a planning folder for the PRD, release plan, architecture notes, and implementation logs.
1.04 | Open |  |  | Create initial configuration files for environment handling, local development, and testing.
1.05 | Open |  |  | Define canonical naming conventions for evaluations, runs, run groups, datasets, scorers, target configurations, runners, and machines.
1.06 | Open |  |  | Create placeholder modules for evaluation definitions, execution engine, run storage, runner adapters, and UI navigation.
1.07 | Open |  |  | Add a project task-tracking file that mirrors this phased release plan.
1.08 | Open |  |  | Update readme.md with project purpose, scope, and current implementation status for Phase 1.
1.09 | Open |  |  | Stage all Phase 1 changes.
1.10 | Open |  |  | Commit all Phase 1 changes with a phase-complete commit message.
1.11 | Open |  |  | Immediately begin Phase 2.

2.01 | Open |  |  | Design the persistence model for EvaluationDefinition, EvaluationVersion, Dataset, DatasetVersion, TestCase, Scorer, ScorerVersion, TargetConfiguration, RunnerProfile, MachineProfile, Run, RunGroup, RunItemResult, RunAggregateMetric, Artifact, TraceReference, and Annotation.
2.02 | Open |  |  | Implement schema definitions or ORM-free persistence structures for all core entities.
2.03 | Open |  |  | Implement immutable versioning behavior for evaluation definitions, scorer versions, and dataset versions.
2.04 | Open |  |  | Implement storage for requested configuration values and effective execution values.
2.05 | Open |  |  | Implement run-group support for matrix and scheduled grouped execution.
2.06 | Open |  |  | Implement storage for tags, notes, and annotations without overwriting immutable execution facts.
2.07 | Open |  |  | Add migration or schema-bootstrap logic for clean local database initialization.
2.08 | Open |  |  | Add repository-level tests for create, read, update, archive, and immutable version behavior.
2.09 | Open |  |  | Update readme.md with the current data model, storage approach, and Phase 2 progress.
2.10 | Open |  |  | Stage all Phase 2 changes.
2.11 | Open |  |  | Commit all Phase 2 changes with a phase-complete commit message.
2.12 | Open |  |  | Immediately begin Phase 3.

3.01 | Open |  |  | Implement RunnerProfile support for Ollama, LM Studio, llama.cpp, MLX or MLX-LM, vLLM, SGLang, TensorRT-LLM, and OpenVINO GenAI.
3.02 | Open |  |  | Define runner metadata fields including runner class, version, supported machine classes, supported model families, parameter surface, and notes.
3.03 | Open |  |  | Implement MachineProfile support for DGX Spark, Apple Silicon MacBook Pro M4 64G, Apple Silicon Mac mini 24G, RTX 4070 desktop, ASUS Vivobook S 15, GTX 1060 6G laptop, and Raspberry Pi edge class.
3.04 | Open |  |  | Define machine metadata fields including hardware class, CPU, GPU or accelerator, RAM, storage summary, runtime stack, availability, and health state.
3.05 | Open |  |  | Implement compatibility rules between runner profiles and machine classes.
3.06 | Open |  |  | Implement machine snapshot capture to persist the exact runtime context used at run time.
3.07 | Open |  |  | Implement requested-machine versus actual-machine recording.
3.08 | Open |  |  | Seed initial runner and machine records for the known lab environments.
3.09 | Open |  |  | Update readme.md with runner coverage, machine coverage, and Phase 3 progress.
3.10 | Open |  |  | Stage all Phase 3 changes.
3.11 | Open |  |  | Commit all Phase 3 changes with a phase-complete commit message.
3.12 | Open |  |  | Immediately begin Phase 4.

4.01 | Open |  |  | Implement CRUD operations for evaluation definitions and versions.
4.02 | Open |  |  | Implement dataset creation, import, versioning, and snapshotting.
4.03 | Open |  |  | Implement test-case tagging, filtering, and subset generation for smoke tests and focused test sets.
4.04 | Open |  |  | Implement scorer definitions for exact match, fuzzy match, rubric scoring, format validation, structured-output validation, latency scoring, cost scoring, and safety scoring.
4.05 | Open |  |  | Implement evaluator-model scorer definitions with model identity, rubric, and parameter capture.
4.06 | Open |  |  | Implement scorer versioning and scorer-set assignment to evaluation definitions.
4.07 | Open |  |  | Implement dataset preview and validation logic for evaluation binding.
4.08 | Open |  |  | Implement validation rules so a run cannot start with missing dataset, scorer, or incompatible schema.
4.09 | Open |  |  | Add test coverage for evaluation versioning, dataset snapshotting, and scorer versioning behavior.
4.10 | Open |  |  | Update readme.md with evaluation, dataset, and scorer capabilities delivered in Phase 4.
4.11 | Open |  |  | Stage all Phase 4 changes.
4.12 | Open |  |  | Commit all Phase 4 changes with a phase-complete commit message.
4.13 | Open |  |  | Immediately begin Phase 5.

5.01 | Open |  |  | Implement target configuration CRUD operations.
5.02 | Open |  |  | Support target configuration fields for machine, runner, model, endpoint, runtime backend, prompt wrapper, inference parameters, context settings, quantization, GPU layer count, batching, and notes.
5.03 | Open |  |  | Implement target configuration cloning for one-variable-at-a-time comparisons.
5.04 | Open |  |  | Implement compatibility validation between target configuration, runner, model family, and machine class.
5.05 | Open |  |  | Implement tagging for target configurations such as baseline, Apple-native, NVIDIA-optimized, Intel-NPU, standard-laptop, old-gpu, and edge.
5.06 | Open |  |  | Implement matrix expansion logic to turn one evaluation plus many target configurations into a run group with child runs.
5.07 | Open |  |  | Implement persistence for requested configuration and effective configuration after runner startup.
5.08 | Open |  |  | Add automated tests for target cloning, compatibility validation, and matrix expansion.
5.09 | Open |  |  | Update readme.md with target configuration and execution-matrix behavior delivered in Phase 5.
5.10 | Open |  |  | Stage all Phase 5 changes.
5.11 | Open |  |  | Commit all Phase 5 changes with a phase-complete commit message.
5.12 | Open |  |  | Immediately begin Phase 6.

6.01 | Open |  |  | Implement run lifecycle state handling for queued, validating, preparing, running generation, running scorers, aggregating, completed, partially completed, failed, blocked, and canceled.
6.02 | Open |  |  | Implement the scheduler for manual, scheduled, batch, and matrix execution.
6.03 | Open |  |  | Implement machine-aware dispatch and runner-aware dispatch.
6.04 | Open |  |  | Implement concurrency limits, queue priorities, and machine reservation logic.
6.05 | Open |  |  | Implement local-only, machine allow-list, runner allow-list, cost cap, time cap, and concurrency cap restrictions.
6.06 | Open |  |  | Implement retry and resume logic for failed items, failed scorers, and interrupted runs.
6.07 | Open |  |  | Implement run progress tracking at both run and run-group level.
6.08 | Open |  |  | Implement scheduler event logging for queue decisions and execution transitions.
6.09 | Open |  |  | Add test coverage for queueing, scheduling, retry, resume, and constraint enforcement.
6.10 | Open |  |  | Update readme.md with scheduler behavior and Phase 6 progress.
6.11 | Open |  |  | Stage all Phase 6 changes.
6.12 | Open |  |  | Commit all Phase 6 changes with a phase-complete commit message.
6.13 | Open |  |  | Immediately begin Phase 7.

7.01 | Open |  |  | Implement a runner adapter interface for model invocation, health check, capability inspection, and metadata capture.
7.02 | Open |  |  | Implement the Ollama adapter.
7.03 | Open |  |  | Implement the LM Studio adapter.
7.04 | Open |  |  | Implement the llama.cpp adapter.
7.05 | Open |  |  | Implement the MLX or MLX-LM adapter.
7.06 | Open |  |  | Implement the vLLM adapter.
7.07 | Open |  |  | Implement the SGLang adapter.
7.08 | Open |  |  | Implement the TensorRT-LLM adapter.
7.09 | Open |  |  | Implement the OpenVINO GenAI adapter.
7.10 | Open |  |  | Implement normalized response capture so all runners feed a common evaluation result format.
7.11 | Open |  |  | Implement runner-version and effective-runtime capture at execution time.
7.12 | Open |  |  | Add adapter tests and compatibility tests for supported runner classes.
7.13 | Open |  |  | Update readme.md with runner adapter coverage and Phase 7 progress.
7.14 | Open |  |  | Stage all Phase 7 changes.
7.15 | Open |  |  | Commit all Phase 7 changes with a phase-complete commit message.
7.16 | Open |  |  | Immediately begin Phase 8.

8.01 | Open |  |  | Implement storage of raw outputs, normalized outputs, scorer outputs, and aggregate metrics.
8.02 | Open |  |  | Implement capture of trace references, token usage, latency breakdowns, retry counts, and cost estimates where available.
8.03 | Open |  |  | Implement execution log storage separate from evaluation artifact storage.
8.04 | Open |  |  | Implement artifact generation for JSON exports, CSV summaries, markdown reports, HTML reports, and comparison bundles.
8.05 | Open |  |  | Implement artifact retention policy support.
8.06 | Open |  |  | Implement rescoring of stored outputs without regeneration when possible.
8.07 | Open |  |  | Implement re-aggregation of run metrics after rescoring.
8.08 | Open |  |  | Add tests for trace capture, artifact generation, and rescoring correctness.
8.09 | Open |  |  | Update readme.md with result-capture and artifact capabilities delivered in Phase 8.
8.10 | Open |  |  | Stage all Phase 8 changes.
8.11 | Open |  |  | Commit all Phase 8 changes with a phase-complete commit message.
8.12 | Open |  |  | Immediately begin Phase 9.

9.01 | Open |  |  | Implement API endpoints for evaluations, datasets, scorers, target configurations, runners, machines, runs, run groups, and reports.
9.02 | Open |  |  | Implement API endpoints for run launch, run resume, scorer retry, item retry, and cancellation.
9.03 | Open |  |  | Implement CLI commands for run launch, run status, run compare, report export, and machine or runner inspection.
9.04 | Open |  |  | Implement machine-readable run launch input suitable for invocation from a Claude Code skill.
9.05 | Open |  |  | Implement authentication or local authorization appropriate for lab use.
9.06 | Open |  |  | Add API and CLI tests covering normal and failure paths.
9.07 | Open |  |  | Produce example automation payloads for scheduled evaluation execution.
9.08 | Open |  |  | Update readme.md with API and CLI usage delivered in Phase 9.
9.09 | Open |  |  | Stage all Phase 9 changes.
9.10 | Open |  |  | Commit all Phase 9 changes with a phase-complete commit message.
9.11 | Open |  |  | Immediately begin Phase 10.

10.01 | Open |  |  | Implement the frontend application shell and routing.
10.02 | Open |  |  | Implement top-level navigation for Evaluations, Datasets, Scorers, Target Configurations, Runs, Run Groups, Machines, Runners, and Reports.
10.03 | Open |  |  | Implement current activity and historical activity separation in the UI.
10.04 | Open |  |  | Implement shared filter state, saved views, and global search across primary entities.
10.05 | Open |  |  | Implement a reusable metadata panel to show evaluation version, dataset version, scorer versions, runner, machine, and target configuration context.
10.06 | Open |  |  | Implement foundational loading, error, empty, and blocked-state handling across the UI.
10.07 | Open |  |  | Add frontend tests for navigation, search, and saved-view behavior.
10.08 | Open |  |  | Update readme.md with frontend foundation and Phase 10 progress.
10.09 | Open |  |  | Stage all Phase 10 changes.
10.10 | Open |  |  | Commit all Phase 10 changes with a phase-complete commit message.
10.11 | Open |  |  | Immediately begin Phase 11.

11.01 | Open |  |  | Implement the evaluation definition list and detail pages.
11.02 | Open |  |  | Implement evaluation create, edit, clone, archive, and version workflows.
11.03 | Open |  |  | Implement dataset list, detail, preview, and subset views.
11.04 | Open |  |  | Implement scorer list, detail, version history, and scorer-set assignment views.
11.05 | Open |  |  | Implement target configuration list, detail, edit, clone, and compare views.
11.06 | Open |  |  | Implement runner inventory and runner detail pages.
11.07 | Open |  |  | Implement machine inventory and machine detail pages.
11.08 | Open |  |  | Add UI tests for evaluation, dataset, scorer, target, runner, and machine management.
11.09 | Open |  |  | Update readme.md with definition-management UI delivered in Phase 11.
11.10 | Open |  |  | Stage all Phase 11 changes.
11.11 | Open |  |  | Commit all Phase 11 changes with a phase-complete commit message.
11.12 | Open |  |  | Immediately begin Phase 12.

12.01 | Open |  |  | Implement the run-launch screen for single-run and matrix-run execution.
12.02 | Open |  |  | Implement launch presets for smoke test, full benchmark, regression check, runner comparison, machine comparison, and rerun failed items.
12.03 | Open |  |  | Implement validation warnings for incompatible machine, runner, model, or cost settings.
12.04 | Open |  |  | Implement the live run list.
12.05 | Open |  |  | Implement the live run detail page with partial results, current stage, failures, and timing.
12.06 | Open |  |  | Implement live run-group monitoring for matrix jobs.
12.07 | Open |  |  | Implement cancel, retry, and resume actions where supported.
12.08 | Open |  |  | Add UI tests for launch workflows and live monitoring.
12.09 | Open |  |  | Update readme.md with run-launch and live-monitoring UI delivered in Phase 12.
12.10 | Open |  |  | Stage all Phase 12 changes.
12.11 | Open |  |  | Commit all Phase 12 changes with a phase-complete commit message.
12.12 | Open |  |  | Immediately begin Phase 13.

13.01 | Open |  |  | Implement the historical run list with filtering by evaluation, model, runner, machine, machine class, scorer, dataset version, date, and status.
13.02 | Open |  |  | Implement the historical run detail page with outputs, metrics, traces, artifacts, and annotations.
13.03 | Open |  |  | Implement side-by-side comparison for at least two runs.
13.04 | Open |  |  | Implement comparison filters for only failures, only disagreements, only changed outcomes, and only regressions.
13.05 | Open |  |  | Implement report generation by evaluation suite, runner, machine class, model family, and date range.
13.06 | Open |  |  | Implement saved report presets and export flows for JSON, CSV, markdown, and HTML.
13.07 | Open |  |  | Add UI and backend tests for historical review, comparison, and reporting.
13.08 | Open |  |  | Update readme.md with historical review and reporting delivered in Phase 13.
13.09 | Open |  |  | Stage all Phase 13 changes.
13.10 | Open |  |  | Commit all Phase 13 changes with a phase-complete commit message.
13.11 | Open |  |  | Immediately begin Phase 14.

14.01 | Open |  |  | Implement local-only enforcement so protected datasets and runs cannot be sent to remote providers.
14.02 | Open |  |  | Implement audit trails for what data was sent to which runner or endpoint.
14.03 | Open |  |  | Implement retention controls for traces, raw outputs, and logs.
14.04 | Open |  |  | Run end-to-end validation across DGX Spark, Apple Silicon, RTX 4070, and Vivobook-class targets where possible.
14.05 | Open |  |  | Run regression tests across core workflows: define, launch, monitor, review, compare, and export.
14.06 | Open |  |  | Fix release-blocking defects and mark tasks Blocked where external dependencies prevent completion.
14.07 | Open |  |  | Prepare release notes for the phased initial release.
14.08 | Open |  |  | Update readme.md with final release status, feature coverage, known limitations, and next steps.
14.09 | Open |  |  | Stage all Phase 14 changes.
14.10 | Open |  |  | Commit all Phase 14 changes with a phase-complete commit message.
14.11 | Open |  |  | Immediately proceed to the next phase of post-release backlog planning.

99.01 | Open |  |  | At the end of every phase, update readme.md to reflect what was delivered, what remains, and any known limitations.
99.02 | Open |  |  | At the end of every phase, stage all changes created during that phase.
99.03 | Open |  |  | At the end of every phase, create a commit with a clear phase-complete commit message.
99.04 | Open |  |  | After committing a phase, immediately begin the next phase unless a task is explicitly marked Blocked.
99.05 | Open |  |  | If a task becomes Blocked, record the blocking reason in the task description or linked implementation log before continuing with unblocked work.
