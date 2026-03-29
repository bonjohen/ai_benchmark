# LLM Runner Comparison Platform — Release Notes

## Overview

The LLM Runner Comparison Platform extends the model evaluation pipeline into a full
runner comparison system. Results are `model x machine x runner x configuration`, not
just `model x machine`. This enables systematic benchmarking across inference runtimes
(Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, OpenVINO GenAI) on
diverse hardware.

## Feature Summary (Phases 1-14)

### Domain Model
- 19 SQLAlchemy tables (added RunnerProfile, TraceReference, Annotation, AuditLogEntry)
- RunnerProfile with runner_class, version, supported_machine_classes, model_families, parameter_surface
- MachineProfile with hardware_class, CPU/GPU/RAM, accelerator_details, runtime_availability
- Run captures requested_config, effective_config, runner_snapshot for reproducibility
- Annotation model for labeling (baseline, regression, preferred) without mutating run records
- AuditLogEntry for tracking data transmission events

### Adapters
- 12 model adapters: OpenAI, Anthropic, Local, GenericHTTP, Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, OpenVINO GenAI
- All inherit from ModelAdapter ABC with generate(), health_check(), capabilities(), get_runtime_metadata()

### Runner/Machine Registry
- 8 pre-seeded runner profiles with full metadata
- 7 pre-seeded machine profiles (DGX Spark, M4 MBP 64G, Mac mini 24G, RTX 4070, Vivobook S 15, GTX 1060, RPi)
- Compatibility rules (static matrix + dynamic machine_class matching)
- Machine snapshot capture for reproducibility

### Execution
- RunOrchestrator with 3-stage lifecycle (create -> execute -> score/finalize)
- Dispatch engine with machine-aware routing, constraint enforcement, concurrent run limits
- Run resume for failed/partially completed runs
- Matrix execution (run-matrix CLI) for multi-target evaluation

### API & CLI
- ~50 REST endpoints under /api/eval/
- API key authentication (X-API-Key / Bearer)
- 10 CLI subcommands: run, run-matrix, status, list, compare, export, rescore, serve, runners, machines

### Frontend (22 templates)
- Sectioned navigation: Definitions, Infrastructure, Execution, Analysis
- Dashboard with current activity vs recent history
- Entity pages: evaluations, datasets, scorers, targets, machines, runners, run groups
- Run launch with presets (smoke, full, regression, runner/machine comparison)
- Live monitoring with cancel/resume
- Historical run list with multi-field filtering
- Run detail with Results, Traces, Metrics, Artifacts tabs
- Side-by-side comparison with disagreement/failure/regression filters
- Global search across all entities
- Reports dashboard with Chart.js visualizations and export (JSON, CSV, HTML, Markdown)

### Privacy & Security
- Local-only enforcement: datasets/runs/targets marked local_only cannot be sent to remote providers
- Provider classification: local (ollama, lmstudio, llamacpp, mlx, vllm, sglang, tensorrt, openvino) vs remote (openai, anthropic)
- Audit trails: AuditLogEntry records data_sent, data_received, run lifecycle events
- Retention controls: configurable cleanup for artifacts, traces, and raw outputs by age

### Scoring
- 8 built-in scorers: exact_match, fuzzy_match, rubric, format_validator, latency_cost, safety, model_judge
- Rescoring support (rescore completed runs with new scorer configs)
- Artifact generation in 4 formats per run

## Known Limitations

- End-to-end hardware validation (task 162) requires physical access to target machines; marked as environment-dependent
- Actual model execution requires a running inference server; the UI launch flow creates run records but does not invoke the orchestrator inline
- Privacy enforcement is advisory (logged warnings) rather than hard-blocking at the adapter level

## Test Coverage

603 total tests (397 eval pipeline + 206 core pipeline), 2 known failures in test_cli.py.
