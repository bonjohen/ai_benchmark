# Naming Conventions

Canonical naming for all entities in the evaluation pipeline and runner comparison platform.

## Entity Names

| Entity | DB Table | Python Class | API Path Segment | CLI Noun |
|---|---|---|---|---|
| Evaluation Definition | `evaluation_definitions` | `EvaluationDefinition` | `/evaluations` | `evaluation` |
| Evaluation Version | `evaluation_versions` | `EvaluationVersion` | `/evaluations/{id}/versions` | — |
| Dataset | `datasets` | `Dataset` | `/datasets` | `dataset` |
| Dataset Version | `dataset_versions` | `DatasetVersion` | `/datasets/{id}/versions` | — |
| Test Case | `test_cases` | `TestCase` | `/datasets/{id}/versions/{vid}/items` | — |
| Scorer | `scorers` | `Scorer` | `/scorers` | `scorer` |
| Scorer Version | `scorer_versions` | `ScorerVersion` | `/scorers/{id}/versions` | — |
| Target Configuration | `target_configurations` | `TargetConfiguration` | `/targets` | `target` |
| Runner Profile | `runner_profiles` | `RunnerProfile` | `/runners` | `runner` |
| Machine Profile | `machine_profiles` | `MachineProfile` | `/machines` | `machine` |
| Machine Snapshot | `machine_snapshots` | `MachineSnapshot` | `/machines/{id}/snapshot` | — |
| Run | `runs` | `Run` | `/runs` | `run` |
| Run Group | `run_groups` | `RunGroup` | `/runs/batch` | `run-group` |
| Run Item Result | `run_item_results` | `RunItemResult` | `/runs/{id}/items` | — |
| Run Aggregate Metric | `run_aggregate_metrics` | `RunAggregateMetric` | `/runs/{id}/metrics` | — |
| Artifact | `artifacts` | `Artifact` | `/runs/{id}/artifacts` | `artifact` |
| Trace Reference | `trace_references` | `TraceReference` | `/runs/{id}/items/{iid}/traces` | — |
| Annotation | `annotations` | `Annotation` | `/annotations` | `annotation` |

## Runner Classes

Canonical `runner_class` values used in `RunnerProfile` and throughout the system:

| Runner Class | Display Name | Description |
|---|---|---|
| `ollama` | Ollama | Cross-platform baseline runner |
| `lmstudio` | LM Studio | Desktop interactive runner |
| `llamacpp` | llama.cpp | Portable low-level reference runner |
| `mlx` | MLX / MLX-LM | Apple-native runner (Metal) |
| `vllm` | vLLM | Server-style throughput runner |
| `sglang` | SGLang | High-performance serving runner |
| `tensorrt` | TensorRT-LLM | NVIDIA-native optimized runner |
| `openvino` | OpenVINO GenAI | Intel AI hardware runner (NPU) |

## Machine Classes

Canonical `hardware_class` values used in `MachineProfile`:

| Hardware Class | Description |
|---|---|
| `dgx_spark` | NVIDIA DGX Spark 128 GB — primary high-capability environment |
| `apple_silicon_pro` | Apple Silicon MacBook Pro M4 64 GB (backlog) |
| `apple_silicon_mini` | Apple Silicon Mac mini 24 GB |
| `rtx_desktop` | RTX 4070 desktop workstation |
| `intel_ai_laptop` | ASUS Vivobook S 15 — Intel Core Ultra 7 155H + NPU (backlog) |
| `old_gpu_laptop` | GTX 1060 6 GB laptop (backlog) |
| `edge_device` | Raspberry Pi + accelerator (backlog) |

## Target Configuration Tags

Canonical tags for `TargetConfiguration.tags`:

| Tag | Meaning |
|---|---|
| `baseline` | Reference configuration for comparison |
| `apple-native` | Uses Apple-specific runtime (MLX/Metal) |
| `nvidia-optimized` | Uses NVIDIA-specific runtime (TensorRT/CUDA) |
| `intel-npu` | Uses Intel NPU acceleration (OpenVINO) |
| `standard-laptop` | Consumer laptop-class hardware |
| `old-gpu` | Legacy GPU with constrained VRAM |
| `edge` | Edge/embedded hardware class |
| `long-context` | Configured for extended context window |
| `coding` | Optimized for code generation tasks |
| `private-only` | Must not send data to remote providers |
| `cheap-runner` | Low resource / cost-optimized config |

## Provider Strings

The `provider` field on `TargetConfiguration` maps to adapter registration:

| Provider | Adapter Class | Notes |
|---|---|---|
| `ollama` | `OllamaAdapter` | Local Ollama server |
| `lmstudio` | `LMStudioAdapter` | Local LM Studio server |
| `llamacpp` | `LlamaCppAdapter` | Local llama-server |
| `mlx` | `MLXAdapter` | Apple Silicon only |
| `vllm` | `VLLMAdapter` | Local vLLM serve |
| `sglang` | `SGLangAdapter` | Local SGLang server |
| `tensorrt` | `TensorRTAdapter` | NVIDIA GPU only |
| `openvino` | `OpenVINOAdapter` | Intel hardware |
| `openai` | `OpenAIAdapter` | Remote OpenAI API |
| `anthropic` | `AnthropicAdapter` | Remote Anthropic API |
| `local_ollama` | `LocalAdapter` | Legacy — use `ollama` instead |
| `local_vllm` | `LocalAdapter` | Legacy — use `vllm` instead |
| `local_llamacpp` | `LocalAdapter` | Legacy — use `llamacpp` instead |
| `generic_http` | `GenericHTTPAdapter` | Custom OpenAI-compat endpoint |
