# Requirements Document: Model Evaluation Pipeline and Evaluation UI

## 1. Purpose

This feature set provides a structured evaluation system for comparing models across machines, runtimes, and configuration values by executing identical tests under controlled conditions. The goal is to let a user define an evaluation once, run it repeatedly across many model configurations, and review the results in a way that makes differences in quality, speed, cost, and stability easy to understand.

The first purpose of the system is operational. It must let the user answer questions like which model performs best for a task, which configuration performs best on a given machine, whether a quantized model is “good enough,” and whether a smaller or cheaper option is close enough to a stronger baseline. The second purpose is historical. It must preserve run history, dataset versions, scorer versions, machine context, and model configuration so that results can be compared over time instead of only at the moment they are generated.

The design should follow patterns that are now common in modern evaluation systems. Current platforms such as OpenAI Evals, W&B Weave, MLflow, Langfuse, Patronus, promptfoo, and lm-eval-harness all treat evaluation as the combination of a dataset, a target model or function, scoring logic, and a run record with viewable results, comparison capability, and repeatability. OpenAI’s Evals API explicitly supports running an evaluation against different models and model parameters; Weave centers evaluation around datasets, scorers, models, and repeated runs; MLflow emphasizes run logging, metrics, artifacts, and result tables; Langfuse exposes per-item results, evaluations, trace IDs, and dataset-run URLs; promptfoo provides matrix-style comparisons and a web viewer; Patronus focuses on side-by-side experiments across models, prompts, and evaluators; and lm-eval-harness supports exporting samples for visualization tools such as W&B and Zeno. ([OpenAI Platform][1])

## 2. Scope

This feature covers the evaluation pipeline and the user-facing evaluation tool. It is not the source-discovery pipeline and it is not the general search/import pipeline already under construction. It sits beside those systems and consumes their outputs where useful, especially datasets, model metadata, and machine metadata.

The feature must support repeated execution of the same test corpus against multiple target configurations. A target configuration includes at minimum a model identity, provider or local endpoint, machine, runtime, parameter set, and execution profile. The system must let the user run the same evaluation across many targets in a controlled way and then compare results at the run level, example level, scorer level, and system-performance level.

The feature must include a user interface for managing evaluation metadata, triggering runs, viewing live status, browsing results, and comparing historical runs. It must also include backend support for scheduling, queueing, run orchestration, trace capture, and persistence of full evaluation state.

## 3. Core Design Principles

The system shall treat an evaluation as a first-class object. An evaluation definition must be stable, versioned, and reusable. A run must always point back to the exact evaluation definition, dataset version, scorer version, target configuration, and machine context used at execution time.

The system shall separate definitions from executions. A dataset is not a run. A scorer is not a run. A model profile is not a run. A machine profile is not a run. This separation is necessary so that the same evaluation can be re-executed months later and still be compared honestly.

The system shall preserve all meaningful metadata. If the user changes temperature, prompt template, quantization level, context size, runtime backend, GPU layer count, or machine, those changes must be visible in the run record and comparison UI. Silent differences are unacceptable.

The system shall support both quality evaluation and operational evaluation. Quality includes correctness, style, format, and rubric-based scoring. Operational behavior includes latency, throughput, token usage, error rate, retry count, and cost where applicable. This reflects the way current systems combine output scoring with observability and trace analysis. ([Weights & Biases Documentation][2])

## 4. Primary User Stories

A user shall be able to define an evaluation suite once and run it against several models on different machines without rewriting the test set. The user shall be able to compare a hosted frontier model, a local large model, a smaller quantized model, and an older-hardware execution profile using the same examples and scorers.

A user shall be able to create a target configuration that specifies model name, endpoint, runtime, prompt wrapper, inference parameters, and machine assignment. The user shall then be able to queue an evaluation run against that target and optionally queue the same evaluation against many other targets.

A user shall be able to open a run and see summary metrics, example-level outputs, scorer breakdowns, machine context, failures, traces, and artifacts. The user shall be able to compare two or more runs side by side and inspect where one configuration wins or loses.

A user shall be able to review historical activity by evaluation, by model family, by machine, by scorer, by dataset, by provider, and by time range. The user shall be able to detect regressions, improvements, instability, and machine-specific behavior.

## 5. Functional Requirements

### 5.1 Evaluation Definitions

The system shall allow creation and editing of evaluation definitions. Each evaluation definition shall include a name, description, owner, tags, dataset binding, scorer binding, execution mode, and optional grouping or suite membership.

The system shall support evaluation definitions that reference either a stored dataset version or a generated dataset snapshot. It shall support both deterministic scorer logic and model-judge or evaluator-model logic. This requirement is aligned with current evaluation platforms that distinguish datasets, scorers, and grading logic as reusable components. ([OpenAI Platform][1])

The system shall version evaluation definitions. Any change to test inputs, prompt templates used by the evaluation harness, scorer logic, pass/fail thresholds, or preprocessing must produce a new immutable definition version or an explicit revision record.

### 5.2 Datasets and Test Cases

The system shall support datasets composed of individual test items. Each item shall store at minimum input, optional expected output, optional context, optional metadata, and optional tags such as task family, difficulty, modality, or failure type.

The system shall support dataset versioning and snapshotting. A run must bind to the exact dataset snapshot used at execution time. The system shall support local datasets and imported datasets. This is consistent with OpenAI datasets and Langfuse experiments, both of which bind runs to specific data inputs and schemas. ([OpenAI Platform][3])

The system shall support filtering datasets into run subsets by tags, machine suitability, token length, modality, or benchmark family. The user must be able to run a smaller smoke test or a larger full evaluation without redefining the underlying dataset.

### 5.3 Scorers and Evaluators

The system shall support multiple scorer types: exact or fuzzy match, rubric-based scorer, format validator, structured-output validator, latency or cost scorer, safety scorer, and evaluator-model scorer. It shall also support aggregation scorers that compute run-level metrics from item-level outcomes.

The system shall support custom scorer definitions and scorer versioning. Each run must record which scorer version was used. If a scorer uses a judge model or remote evaluator, the judge model identity and configuration shall also be stored. This requirement follows current patterns in Weave, OpenAI Evals, and Patronus, which all treat scorer or evaluator configuration as part of the evaluation definition. ([Weights & Biases Documentation][4])

The system shall support both per-item evaluations and aggregate run evaluations. Langfuse’s experiment model is a useful example here, because it preserves both item-level results and run-level evaluations. ([Python Reference][5])

### 5.4 Target Configurations

The system shall support target configuration objects. A target configuration shall include model identity, endpoint or provider, machine assignment, runtime backend, prompt wrapper or system prompt variant, inference parameters, maximum context setting, and any runtime-specific options such as quantization, GPU offload layers, batch size, or temperature.

The system shall support named target profiles so the user can reuse stable configurations such as “DGX Spark / GLM-4.7 / long context,” “RTX 4070 / Qwen 7B / coding,” “Vivobook / HYMT 1.57B / standard laptop,” or “MSI GTX 1060 / small model baseline.” This is necessary because the same model family may behave differently across machines and runtimes.

The system shall allow cloning a target profile and altering one value at a time. This supports controlled comparisons such as same model, different quantization; same machine, different runtime; or same model and runtime, different parameter values.

### 5.5 Run Execution

The system shall let the user trigger a single run, a batch of runs, or a matrix run. A matrix run means executing one evaluation against multiple target configurations under a shared parent job. This is similar in spirit to promptfoo’s side-by-side matrix comparisons and OpenAI’s ability to run evaluations across different models and parameters. ([promptfoo.dev][6])

The system shall support scheduled runs, manual runs, and API-triggered runs. Since the user intends to invoke this through Claude Code as a scheduled agent skill, the system shall expose a machine-readable interface suitable for CLI and scheduled automation.

The system shall record run lifecycle states such as queued, provisioning, running, scoring, completed, failed, canceled, and partially completed. The UI shall expose current state and progress at both the run level and the batch level.

The system shall support retries, resumable scoring, and rerun-from-failure. If generation succeeded but scoring failed, the system should not require full regeneration unless the user requests it.

### 5.6 Traces, Artifacts, and Logs

The system shall store item-level outputs, raw responses, scorer results, aggregate metrics, and execution traces. Where available, the system shall capture trace IDs, token usage, cost estimates, model latency, retry count, and failure messages. This follows the observability patterns visible in Langfuse, W&B Weave, and Patronus. ([Python Reference][5])

The system shall store artifacts such as result tables, JSON exports, HTML comparison views, plots, confusion-style views for categorical scorers, and downloadable raw output bundles. MLflow’s use of metrics, artifacts, and tables is a useful reference model here. ([MLflow AI Platform][7])

The system shall preserve enough raw data to allow later rescoring without re-running generation when appropriate. For example, a stricter rubric scorer should be able to re-grade stored outputs if the user requests it.

## 6. User Interface Requirements

### 6.1 Main Navigation

The UI shall expose at minimum these top-level areas: Evaluations, Datasets, Scorers, Target Configurations, Runs, Machines, and Reports. The user must be able to move from a run to its evaluation definition, dataset version, scorer version, target configuration, and machine record without losing context.

The UI shall present current activity and historical activity distinctly. Current activity should emphasize queue state, run progress, failures, and machine occupancy. Historical activity should emphasize comparisons, trends, and drill-down analysis.

### 6.2 Evaluation Definition UI

The user shall be able to create or edit evaluation definitions in a structured form. The form shall show dataset binding, scorer binding, task description, pass criteria, tags, and default execution settings.

The user shall be able to preview sample cases from the bound dataset and preview the expected input schema for the target model adapter. Current platforms like OpenAI Datasets and Weave demonstrate the value of visual dataset and eval setup before execution. ([OpenAI Platform][3])

### 6.3 Target Configuration UI

The user shall be able to create, duplicate, edit, archive, and tag target configurations. The screen shall show the machine, runtime, model, parameter values, and execution notes in one place.

The UI shall make differences obvious. If two target configurations differ only by temperature, quantization, or context length, the user should see that immediately. Hidden configuration differences are a major source of invalid comparisons and must be avoided.

### 6.4 Run Trigger UI

The UI shall allow the user to select one evaluation and one or more target configurations, then launch either individual runs or a grouped matrix run. The trigger screen shall show estimated workload size, number of examples, expected queue placement, and any warnings about unsupported combinations.

The UI shall support templates for common workflows such as smoke test, full benchmark, regression check, and machine qualification run.

### 6.5 Live Run Monitoring UI

The UI shall display active runs with progress, elapsed time, current machine, item counts, current step, and failure summary. It shall show batch-level progress for matrix runs.

The user shall be able to open a live run and view completed examples as they arrive. This requirement is informed by the value of tracing and live result inspection seen in Weave, Langfuse, and Patronus. ([Weights & Biases Documentation][2])

### 6.6 Historical Run Review UI

The UI shall provide a historical run list with filters for date, model, machine, scorer, evaluation suite, dataset version, tags, and status. The user shall be able to sort by any major metric.

The UI shall show a run detail page with summary metrics, scorer breakdown, per-example outputs, trace links, machine details, and artifacts. The user shall be able to pivot from an aggregate metric to the exact examples that influenced it.

### 6.7 Comparison UI

The UI shall support side-by-side comparison of two or more runs. It shall support comparison at the overall metric level, scorer level, and example level. Promptfoo’s matrix-style comparison and W&B’s table-oriented run comparison are useful precedent for this style of analysis. ([promptfoo.dev][6])

The comparison UI shall answer these questions quickly: which run was best overall, where each run failed, which differences are statistically or practically meaningful, and whether the performance tradeoff is worth the latency or cost change.

The UI shall provide diff views for output text, structured outputs, pass/fail labels, score deltas, and machine/runtime configuration deltas.

## 7. Machine and Environment Metadata Requirements

The system shall maintain machine profiles for every execution host. A machine profile shall include hostname, hardware class, CPU, GPU or accelerator details, RAM, storage summary, operating system, runtime availability, and capacity indicators relevant to local inference.

Each run shall record the machine profile snapshot used at execution time, including runtime version, model-serving backend version, and any notable environment variables or tuning values relevant to reproducibility.

The system shall specifically support the machine classes already described in the lab: DGX Spark, RTX 4070 workstation, MacBook Pro M4, Mac mini M4, standard laptop class, older GTX 1060 laptop class, and edge accelerator class. This is important because the feature’s purpose is to compare models across materially different execution environments.

## 8. Data Model Requirements

The core persisted entities shall include EvaluationDefinition, EvaluationVersion, Dataset, DatasetVersion, TestCase, Scorer, ScorerVersion, TargetConfiguration, MachineProfile, Run, RunItemResult, RunAggregateMetric, Artifact, and TraceReference.

A Run record shall store references to exactly one evaluation version, one dataset version, one scorer version set, one target configuration, and one machine snapshot. Batch or matrix execution shall be represented by a parent run group that links multiple Run records together.

A RunItemResult shall store the source test item, raw output, normalized output if applicable, scorer outputs, pass/fail values, structured errors, token and latency metadata, trace reference, and timestamps.

The system shall preserve immutable execution records. Editable annotations may be layered on top, but the recorded facts of a completed run must not be overwritten.

## 9. Integration Requirements

The system shall expose CLI and API entry points suitable for invocation from a scheduled task inside Claude Code and from agent skills. A run must be creatable without using the UI.

The system shall integrate with the search/data import pipeline only at defined boundaries. Imported model metadata may populate model catalogs. Imported benchmark descriptions may seed datasets. Imported machine metadata may update host profiles. The evaluation feature must not depend on the research pipeline being available at run time.

The system should support adapters to existing evaluation or observability systems where useful. OpenAI Evals, W&B Weave, MLflow, Langfuse, promptfoo, Patronus, and lm-eval-harness show that export/import interoperability, trace linking, and result normalization are practical and valuable. ([OpenAI Platform][1])

## 10. Non-Functional Requirements

The system shall prioritize reproducibility. Two runs using the same evaluation version, dataset version, scorer version, target configuration, and machine profile should be clearly marked as directly comparable.

The system shall prioritize auditability. A user must be able to inspect how a score was produced, which scorer produced it, what input was used, what output was judged, and what machine and runtime generated it.

The system shall prioritize partial failure tolerance. A failed item or scoring step must not necessarily invalidate the entire run. Partial completion should remain visible and analyzable.

The system shall prioritize extensibility. New scorer types, new model providers, new runtimes, and new hardware classes must be addable without redesigning the core data model.

The system shall prioritize local-first privacy where appropriate. Since this lab compares local and remote models, the system shall support marking datasets or runs as local-only so that sensitive examples cannot accidentally be sent to remote endpoints.

## 11. Reporting Requirements

The system shall provide summary reports by evaluation, model family, machine, and date range. Reports shall show quality metrics, latency metrics, cost metrics, stability metrics, and configuration summaries.

The system shall provide downloadable exports in machine-readable form and human-readable form. At minimum this should include JSON, CSV for tabular summaries, and HTML or markdown for run reports.

The system shall support saved views and report presets such as “best coding runs,” “quantization comparison,” “standard laptop viability,” and “older hardware baseline.”

## 12. Acceptance Criteria

A user can define one evaluation suite, bind a dataset and scorer set, and run it against at least three distinct target configurations without redefining the test items.

A user can compare two runs side by side and see differences in aggregate score, scorer breakdown, output samples, latency, and target configuration.

A user can inspect one historical run six weeks later and still determine exactly which model, machine, runtime, parameters, dataset version, and scorer version produced the recorded results.

A user can launch evaluation runs from both the UI and a non-UI automation entry point.

A user can filter historical runs by machine class and determine whether a model configuration was viable on a standard laptop, older GPU hardware, or a stronger inference host.

A user can distinguish between current active work and historical completed work from the main interface without confusion.

## 13. Recommended Initial Release Cut

The initial release should include evaluation definitions, dataset versioning, scorer versioning, target configurations, machine profiles, manual and scheduled run triggering, matrix runs, live status, historical run list, run detail pages, and side-by-side comparison for two runs.

The initial release should also include item-level output storage, aggregate metrics, latency and token metadata, downloadable JSON/CSV exports, and a minimal artifact system for logs and result tables.

The initial release does not need advanced statistical analysis, collaborative annotation, or full external-platform synchronization. Those can follow once the core loop of define, run, inspect, compare, and repeat is solid.

[1]: https://platform.openai.com/docs/api-reference/evals?lang=go&utm_source=chatgpt.com "Evals | OpenAI API Reference"
[2]: https://docs.wandb.ai/models/tables/evaluate-models?utm_source=chatgpt.com "Evaluate models with W&B Weave and W&B Tables - Weights & Biases Documentation"
[3]: https://platform.openai.com/docs/guides/evaluation-getting-started?utm_source=chatgpt.com "Getting started with datasets | OpenAI API"
[4]: https://docs.wandb.ai/weave/guides/core-types/evaluations/?utm_source=chatgpt.com "Evaluations overview - Weights & Biases Documentation"
[5]: https://python.reference.langfuse.com/langfuse/experiment?utm_source=chatgpt.com "langfuse.experiment API documentation"
[6]: https://www.promptfoo.dev/docs/getting-started/?utm_source=chatgpt.com "Getting started | Promptfoo"
[7]: https://mlflow.org/docs/latest/ml/evaluation/model-eval?utm_source=chatgpt.com "Model Evaluation | MLflow"
