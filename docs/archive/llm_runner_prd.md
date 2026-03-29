# Product Requirements Document

## Evaluation Pipeline and Runner Comparison Platform for My AI Lab

## 1. Purpose

This product provides a structured system for evaluating models across different hardware, runners, and configuration values by executing identical tests under controlled conditions. The system must let the user define an evaluation once, run it repeatedly across multiple machines and runner stacks, and inspect the results in a way that makes tradeoffs in quality, speed, stability, compatibility, memory fit, and cost easy to understand.

The central design requirement is that the runner is a first-class experimental variable. A result is not merely “model X on machine Y.” It is “model X with runner Z, on machine Y, with configuration C, against evaluation E, dataset D, and scorer set S.” The product must preserve and expose that full context everywhere a result is created, viewed, compared, or exported.

This feature set is intended to operate alongside the existing research and data-import work already underway. The research pipeline discovers models, providers, runners, hardware data, and related information. This product focuses on controlled execution, evaluation, comparison, historical review, and decision support.

## 2. Background and Problem Statement

The lab now includes materially different execution environments. The NVIDIA DGX Spark 128 GB serves as the primary high-capability local environment. Apple Silicon systems include a MacBook Pro M4 with 64 GB and a Mac mini with 24 GB. The RTX 4070 desktop represents a mainstream powerful GPU workstation. The ASUS Vivobook S 15 OLED with Intel Core Ultra 7 155H introduces built-in Intel AI hardware and must be evaluated both as a normal laptop and as an AI PC. Backlog platforms include an older GTX 1060 6 GB laptop and a Raspberry Pi class edge device with NPU or accelerator hardware.

The same model may behave differently depending on the runner used to host it. A runner such as Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, or OpenVINO GenAI may change model compatibility, memory use, speed, system behavior, service behavior, or practical fit for a given machine. Today there is no single structured product in the lab that allows the user to systematically answer questions such as which runner is best for Apple Silicon, which runner is best for the DGX Spark, whether a model is viable on a standard laptop, or whether the Intel NPU path changes the result enough to matter.

The product must solve that problem by giving the user a repeatable way to define evaluations, execute them across runner and machine combinations, preserve all relevant metadata, and review the results historically.

## 3. Product Goals

The first goal is to allow identical evaluations to be executed across multiple combinations of model, runner, machine, and configuration without redefining the test set.

The second goal is to expose runner choice as a first-class comparison dimension in the user interface, in stored metadata, and in exported reports.

The third goal is to support both day-to-day experimentation and longer-term historical analysis. The user must be able to compare current results with older runs and still know exactly what changed.

The fourth goal is to support automated execution through a scheduled agent within a Claude Code skill, while also supporting direct manual use through a user interface.

The fifth goal is to provide a useful operational tool, not just a record of results. The user should be able to see what is currently running, what ran in the past, what failed, what improved, what regressed, and which hardware or runner combinations are worth further investment.

## 4. Non-Goals

This product is not the source-discovery system. It does not replace the search and data-import pipeline.

This product is not a general benchmark hosting platform for the public internet. It is an internal evaluation tool for the lab.

This product is not initially responsible for training, fine-tuning, or large-scale distributed experimentation. It is focused on execution and evaluation of models already available through local or remote runners.

This product is not initially required to provide collaborative multi-user workflow, permissions administration beyond practical local needs, or enterprise-grade tenancy separation.

## 5. Users and Primary Use Cases

The primary user is the lab owner, who needs to compare runners, models, hardware, and configuration values under controlled conditions and make practical decisions about what to run where.

A secondary user is a coding or research agent operating through a scheduled skill or automation entry point. That user does not need the full visual interface, but it must be able to trigger runs, query status, and retrieve results.

The primary use cases are straightforward. The user defines an evaluation suite and runs it against multiple target configurations. The user creates or edits a target configuration that includes machine, runner, model, and runtime parameters. The user launches a grouped run across several targets. The user watches live progress. The user compares historical runs side by side. The user reviews which runner works best on the DGX Spark, which runner works best on Apple Silicon, and whether a consumer laptop or older GPU is viable for a given model family.

## 6. Product Principles

The system must treat the runner as part of the experiment, not as an implementation detail.

The system must preserve all execution context needed for honest comparison. Silent changes are unacceptable.

The system must separate definitions from executions. Evaluation definitions, datasets, scorers, target configurations, machine profiles, and runs are distinct objects.

The system must support both quality and operational evaluation. It is not enough to know which output is better if the latency, fit, failure rate, or cost makes it impractical.

The system must support local-first experimentation while allowing remote-hosted models when required.

The system must favor reproducibility, auditability, and controlled comparison over convenience shortcuts that erase context.

## 7. Core Concepts

An evaluation is a reusable definition of a test. It includes the dataset or dataset snapshot, one or more scorers, optional execution notes, and thresholds or tags.

A dataset is a set of test items. Each test item contains the input, optional expected output, optional context, optional metadata, and tags.

A scorer is a mechanism that grades output. It may be deterministic, rule-based, judge-model based, or aggregate-only.

A target configuration is the full execution description. It includes the machine, runner, model identity, runtime backend, prompt wrapper or system template if applicable, and all relevant runtime parameters.

A machine profile describes the host environment, including hardware class and software stack.

A run is one execution of one evaluation against one target configuration on one machine snapshot.

A run group is a parent container for related runs, such as a matrix run or scheduled batch.

A runner is the hosting or inference layer used to execute the model. Examples include Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, and OpenVINO GenAI.

## 8. Functional Requirements

### 8.1 Evaluation Definitions

The system shall allow the user to create, edit, clone, archive, and version evaluation definitions.

Each evaluation definition shall include a name, description, tags, owner, dataset binding, scorer binding, execution notes, optional thresholds, and optional grouping into a suite.

Any meaningful change to inputs, evaluation logic, prompt wrappers used by the harness, thresholds, or preprocessing shall result in a new immutable definition version or explicit recorded revision.

The system shall allow a single evaluation to be executed against many target configurations without changing the evaluation definition itself.

### 8.2 Datasets and Test Cases

The system shall support datasets composed of individual test items.

Each test item shall store the input, optional expected output, optional context, optional source, optional tags, and optional metadata such as task family, difficulty, modality, or benchmark mapping.

The system shall support dataset versioning and snapshotting so that each run binds to an exact dataset state.

The system shall support dataset subsets, including smoke test subsets, benchmark subsets, machine-specific subsets, token-length subsets, and tagged subsets.

The system shall support imported datasets and manually curated datasets.

### 8.3 Scorers and Evaluators

The system shall support exact match, fuzzy match, rubric-based scoring, format validation, structured-output validation, safety or policy scoring, latency scoring, cost scoring, and evaluator-model scoring.

The system shall support multiple scorers applied to the same output.

The system shall version scorers independently of evaluations.

If a scorer uses a judge model or remote evaluation layer, the system shall record the evaluator model identity, evaluator parameters, prompt or rubric used, and any retry behavior.

The system shall support re-scoring previously generated outputs without requiring regeneration when sufficient raw data is stored.

The system shall support scorer failure handling and scorer-only retry.

### 8.4 Target Configurations

The system shall support target configuration objects that include machine assignment, runner, runner version where known, model identity, model version or slug where known, provider or endpoint, runtime backend, parameter set, context setting, and runtime-specific options.

The system shall support reusable named target profiles for combinations such as DGX Spark plus SGLang plus model A, Apple Silicon plus MLX plus model B, or Vivobook plus OpenVINO GenAI plus HYMT 1.57B.

The system shall support cloning and small edits to target configurations for controlled comparisons.

The system shall record both requested configuration and effective configuration at execution time. If the runner adjusts or ignores a requested parameter, that must be visible.

The system shall support tags such as baseline, Apple-native, NVIDIA-optimized, Intel-NPU, standard-laptop, old-gpu, edge, long-context, coding, private-only, and cheap-runner.

### 8.5 Runner Support

The system shall treat runner identity as a required field of every executable target configuration.

The system shall support at minimum the following runner classes in the data model and UI: Ollama, LM Studio, llama.cpp, MLX or MLX-LM, vLLM, SGLang, TensorRT-LLM, and OpenVINO GenAI.

The system shall allow additional runners to be added later without schema redesign.

The system shall expose runner as a filter, comparison dimension, reporting dimension, and required export field.

The system shall allow a user to ask and answer questions such as which runner performs best for a given model on Apple Silicon, which runner is best on DGX Spark, and whether a runner provides material benefit on Intel NPU hardware.

### 8.6 Run Execution

The system shall support single runs, scheduled runs, batch runs, and matrix runs.

A matrix run shall be defined as one evaluation executed against multiple target configurations under a shared parent run group.

The system shall expose machine-readable interfaces for scheduled execution, CLI triggering, and agent-based invocation from Claude Code skills.

The system shall record lifecycle states including queued, validating, preparing, running generation, running scorers, aggregating, completed, partially completed, failed, and canceled.

The system shall support retries, rerun failed items, rerun failed scorers, rerun from checkpoint, and intentional full rerun.

The system shall support constraints such as local-only, machine allow-list, runner allow-list, cost cap, time cap, and concurrency cap.

The scheduler shall be machine-aware and compatibility-aware.

### 8.7 Traces, Artifacts, and Logs

The system shall store raw outputs, normalized outputs where applicable, scorer outputs, aggregate metrics, failure records, trace references, token usage, latency metadata, and cost estimates where available.

The system shall distinguish between execution logs and evaluation artifacts.

The system shall support artifact retention policies for raw logs, traces, and export bundles.

The system shall provide downloadable bundles for a run or run group.

The system shall preserve enough raw data to allow rescoring and later review.

### 8.8 Historical Comparison

The system shall provide run comparison at the overall, scorer, and item levels.

The system shall allow comparison by model, runner, machine, machine class, dataset version, scorer version, evaluation version, tag, and time window.

The system shall support side-by-side comparison of at least two runs in the first release and should support multi-run comparison thereafter.

The system shall make disagreements, failures, regressions, and meaningful deltas easy to inspect.

### 8.9 Reports and Exports

The system shall generate reports by evaluation, model family, runner, machine class, and time range.

Reports shall show quality metrics, latency metrics, cost metrics, failure summaries, and configuration summaries.

The system shall export machine-readable and human-readable outputs, including JSON, CSV, markdown, and HTML where appropriate.

The system shall support saved views and repeatable report presets.

## 9. User Interface Requirements

### 9.1 Main Navigation

The UI shall expose at minimum Evaluations, Datasets, Scorers, Target Configurations, Runs, Run Groups, Machines, Runners, and Reports.

The UI shall clearly distinguish current activity from historical activity.

The UI shall support search, filters, and saved views across all primary entities.

### 9.2 Evaluation Definition UI

The UI shall allow creation, editing, versioning, archiving, and preview of evaluation definitions.

The UI shall show bound dataset version, scorer versions, thresholds, tags, and notes.

The UI shall allow sample preview before execution.

### 9.3 Dataset UI

The UI shall allow browsing datasets, dataset versions, and test items.

The UI shall support filtering by tags, source, modality, and difficulty.

The UI shall allow the user to create subset views for smoke tests or targeted experiments.

### 9.4 Target Configuration UI

The UI shall allow creation, editing, duplication, archiving, tagging, and comparison of target configurations.

The UI shall highlight machine, runner, model, runtime, and parameter differences clearly.

The UI shall validate compatibility before launch and show warnings for likely invalid combinations.

### 9.5 Runner UI

The UI shall provide a dedicated runner inventory view.

Each runner record shall describe runner class, known compatible machine classes, known supported model families, known parameter fields, and notes on operational behavior.

The runner detail page shall show recent runs, recent failures, performance trends by machine, and links to target configurations that use that runner.

### 9.6 Run Trigger UI

The UI shall allow the user to choose an evaluation, choose one or more target configurations, and launch either a single run or grouped matrix run.

The launch screen shall show sample count, selected runners, selected machines, estimated workload, and warnings about unsupported combinations or likely resource issues.

The launch screen shall allow preset launch modes such as smoke test, full benchmark, regression check, runner comparison, machine comparison, and rerun failed items.

### 9.7 Live Run Monitoring UI

The UI shall show active runs with progress, stage, elapsed time, machine, runner, current item counts, and failures.

For matrix runs, the UI shall show both parent group status and child run status.

The user shall be able to inspect partial results during execution.

### 9.8 Historical Run Review UI

The UI shall support filtering historical runs by evaluation, model, runner, machine, machine class, scorer, dataset version, date, and status.

The run detail page shall show the full execution context, including runner, runner version if known, machine snapshot, model, runtime, parameter values, outputs, scorer results, traces, and artifacts.

The UI shall support annotations such as baseline, regression, obsolete, unstable, or preferred.

### 9.9 Comparison UI

The UI shall support side-by-side comparison of runs.

Comparison shall include output diffs, scorer diffs, latency diffs, cost diffs, runner differences, and machine differences.

The UI shall allow filtering to changed examples, only failures, only disagreements, or only performance regressions.

### 9.10 Reports UI

The UI shall provide reusable reports and saved views by runner, machine, model family, and evaluation suite.

The UI shall allow export and sharing of report bundles for offline review.

## 10. Machine and Environment Requirements

The system shall maintain machine profiles for every host.

Each machine profile shall include hostname, hardware class, CPU, GPU or accelerator details, RAM, storage summary, operating system, runtime stack, and capacity or health indicators.

The system shall explicitly support and model the following classes in initial planning: DGX Spark 128 GB primary environment, Apple Silicon MacBook Pro M4 64 GB, Apple Silicon Mac mini 24 GB, RTX 4070 desktop, ASUS Vivobook S 15 OLED with Intel Core Ultra 7 155H and Intel AI hardware, and backlog classes for GTX 1060 6 GB laptop and Raspberry Pi plus edge accelerator.

Each run shall store the exact machine snapshot used at execution time, including runtime versions and notable environment values relevant to reproducibility.

If the actual host differs from the requested machine or machine class, the run record shall show both values.

## 11. Integration Requirements

The system shall expose a CLI and API interface suitable for invocation by a scheduled Claude Code task inside a skill.

The system shall support integration points for imported model metadata, imported machine metadata, imported benchmark descriptions, and other structured information produced by the research and import pipeline.

The evaluation system shall not require the research pipeline to be online at run time.

The system should support adapters or export paths for external evaluation or observability systems where that creates practical value, but those integrations are not required for initial delivery.

## 12. Security and Privacy Requirements

The system shall support marking datasets, evaluations, target configurations, or runs as local-only.

The scheduler and execution system shall prevent local-only workloads from being sent to remote providers.

The system shall preserve auditability for what data was sent where and by which runner.

The system shall support retention controls for sensitive outputs, traces, and logs.

## 13. Non-Functional Requirements

The system shall prioritize reproducibility. Directly comparable runs must be clearly marked.

The system shall prioritize auditability. A user must be able to determine exactly how a score was produced and what was executed.

The system shall prioritize partial failure tolerance. A run with partial success must remain analyzable.

The system shall prioritize extensibility. New runners, new scorers, new machine classes, and new model providers must be addable without redesigning the system.

The system shall prioritize performance appropriate to lab-scale usage. The interface must remain usable with a meaningful historical backlog of runs, datasets, and artifacts.

## 14. Data Model Requirements

The core persisted entities shall include EvaluationDefinition, EvaluationVersion, Dataset, DatasetVersion, TestCase, Scorer, ScorerVersion, TargetConfiguration, RunnerProfile, MachineProfile, Run, RunGroup, RunItemResult, RunAggregateMetric, Artifact, TraceReference, and Annotation.

A TargetConfiguration shall require references to both a runner and a machine class or machine target.

A Run shall bind exactly one evaluation version, one dataset version, one scorer version set, one target configuration, one runner snapshot, and one machine snapshot.

A RunGroup shall link related runs produced by a matrix execution or scheduled batch.

A RunItemResult shall store item input reference, raw output, normalized output if applicable, scorer results, pass or fail status, latency metadata, token metadata, failure metadata, and trace references.

A RunAggregateMetric shall store pass rate, mean score, latency summary, cost summary, failure counts, and other derived results.

Artifacts shall reference generated outputs such as reports, tables, logs, plots, exports, or comparison bundles.

Execution facts shall be immutable once recorded. User annotations may be added without rewriting historical facts.

## 15. Acceptance Criteria

A user can define an evaluation suite once and run it against at least three target configurations that differ by runner, machine, or both.

A user can compare the same model across at least two different runners on the same machine and see the result differences clearly.

A user can compare the same runner across at least two machine classes and see the result differences clearly.

A user can inspect a historical run weeks later and still identify the exact evaluation version, dataset version, scorer version, runner, runner-relevant settings, machine, and model configuration used.

A user can launch runs from both the UI and a non-UI automation entry point.

A user can filter historical runs by runner and determine which runner produced the best result for a given model and machine class.

A local-only dataset cannot be accidentally executed through a remote-only target.

A matrix run can be launched, monitored, and reviewed as a grouped object.

## 16. Initial Release Requirements

The first release must include evaluation definitions, dataset versioning, scorer versioning, target configurations, runner profiles, machine profiles, manual run launch, scheduled run launch, grouped matrix runs, live status, historical run list, run detail pages, and side-by-side run comparison.

The first release must include runner as a first-class filter, field, and comparison dimension.

The first release must include support for the primary hardware currently in scope and enough schema flexibility to represent the backlog hardware classes.

The first release must include raw output storage, scorer output storage, aggregate metrics, latency and token metadata where available, downloadable JSON and CSV exports, and a minimal artifact system.

The first release does not need advanced statistical significance testing, collaborative annotation workflows, or full third-party synchronization.

## 17. Future Work

Future work may include broader community benchmark import, deeper statistical analysis, automated recommendation logic for best runner by machine class, runner-specific tuning assistants, collaborative review workflows, and richer visualization of long-term trend lines.

Future work may also include automatic runner recommendation based on historical fit data, such as suggesting MLX on Apple Silicon for a given model family, TensorRT-LLM or SGLang on DGX Spark, or OpenVINO GenAI on Intel AI hardware when historical evidence supports it.
