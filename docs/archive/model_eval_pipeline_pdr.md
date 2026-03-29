# Physical Design Requirements: Model Evaluation Pipeline and Evaluation UI

**Source document:** `docs/model_eval_pipeline_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-28

---

## 1. System Context

This PDR describes the physical implementation of the Model Evaluation Pipeline feature. It sits alongside (but is independent of) the existing source-discovery pipeline in `ai_benchmark/`. The evaluation pipeline adds a new top-level package `ai_benchmark/eval/` with its own models, services, API, CLI commands, and UI.

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| SQLAlchemy async engine + session factory | `ai_benchmark/models/base.py` | Shared — use same `Base`, `create_engine()`, `create_session_factory()` |
| Alembic migrations | `alembic/` | Shared — new eval tables go in new migration files in `alembic/versions/` |
| Pydantic settings pattern | `ai_benchmark/config/settings.py` | Extend `PipelineSettings` or create parallel `EvalSettings` |
| Click CLI group | `ai_benchmark/cli.py` | Add `eval` subcommand group to existing `cli` Click group |
| structlog logging | `ai_benchmark/main.py` | Shared — same `configure_logging()` |
| pytest + pytest-asyncio + conftest | `tests/conftest.py` | Shared — extend `db_engine` fixture to include eval models |
| pyproject.toml | `pyproject.toml` | Add new dependencies (FastAPI, uvicorn, Jinja2 or React build) |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| `fastapi` | REST API for eval pipeline + UI backend | `>=0.110` |
| `uvicorn[standard]` | ASGI server | `>=0.27` |
| `jinja2` | Server-side templating for eval UI | `>=3.1` |
| `python-multipart` | FastAPI file upload support | `>=0.0.9` |
| `httpx` | Already present — used for model endpoint calls | (existing) |

---

## 2. Package Layout

```
ai_benchmark/
  eval/                          # NEW — entire evaluation subsystem
    __init__.py
    models/
      __init__.py
      evaluation.py              # EvaluationDefinition, EvaluationVersion
      dataset.py                 # Dataset, DatasetVersion, TestCase
      scorer.py                  # Scorer, ScorerVersion
      target.py                  # TargetConfiguration
      machine.py                 # MachineProfile, MachineSnapshot
      run.py                     # Run, RunGroup, RunItemResult, RunAggregateMetric
      artifact.py                # Artifact, TraceReference
    services/
      __init__.py
      eval_service.py            # CRUD for evaluation definitions + versions
      dataset_service.py         # CRUD for datasets, versions, test cases
      scorer_service.py          # CRUD for scorers + versions
      target_service.py          # CRUD for target configurations
      machine_service.py         # CRUD for machine profiles + snapshots
      run_service.py             # Run lifecycle: create, queue, update status, finalize
      comparison_service.py      # Side-by-side run comparison logic
      report_service.py          # Aggregation, export, saved views
    execution/
      __init__.py
      orchestrator.py            # Run orchestration: queue → provision → execute → score → finalize
      executor.py                # Item-level execution: send prompt, capture response + traces
      adapters/
        __init__.py
        base.py                  # Abstract ModelAdapter interface
        openai_adapter.py        # OpenAI / compatible API adapter
        anthropic_adapter.py     # Anthropic API adapter
        local_adapter.py         # Local inference (llama.cpp, vLLM, Ollama, etc.)
        generic_http_adapter.py  # Generic HTTP endpoint adapter
    scoring/
      __init__.py
      scorer_runner.py           # Dispatches scoring for a run
      builtin/
        __init__.py
        exact_match.py           # Exact / fuzzy match scorer
        rubric.py                # Rubric-based scorer
        format_validator.py      # Format / structured-output validator
        latency_cost.py          # Latency, token usage, cost scorer
        safety.py                # Safety scorer
        model_judge.py           # LLM-as-judge scorer
    api/
      __init__.py
      app.py                     # FastAPI app factory
      routes/
        __init__.py
        evaluations.py           # /api/eval/evaluations
        datasets.py              # /api/eval/datasets
        scorers.py               # /api/eval/scorers
        targets.py               # /api/eval/targets
        machines.py              # /api/eval/machines
        runs.py                  # /api/eval/runs
        comparisons.py           # /api/eval/comparisons
        reports.py               # /api/eval/reports
      schemas/
        __init__.py
        evaluation.py            # Pydantic request/response schemas
        dataset.py
        scorer.py
        target.py
        machine.py
        run.py
        comparison.py
        report.py
    ui/
      __init__.py
      server.py                  # Mounts static files + Jinja2 templates
      templates/                 # Jinja2 HTML templates
        base.html
        evaluations/
          list.html
          detail.html
          create.html
        datasets/
          list.html
          detail.html
        targets/
          list.html
          detail.html
        runs/
          list.html
          detail.html
          live.html
        comparisons/
          compare.html
        reports/
          dashboard.html
      static/
        css/
        js/
    cli/
      __init__.py
      commands.py                # Click commands: eval run, eval status, eval list, eval compare, eval export
tests/
  test_eval/
    __init__.py
    test_eval_models.py
    test_dataset_service.py
    test_scorer_runner.py
    test_orchestrator.py
    test_executor.py
    test_comparison_service.py
    test_api/
      __init__.py
      test_evaluations_api.py
      test_runs_api.py
      test_comparisons_api.py
    fixtures/
      sample_dataset.json
      sample_scorer.py
      sample_target.json
```

---

## 3. Data Model — Complete Schema Definitions

All models inherit from the existing `ai_benchmark.models.base.Base`. All use `mapped_column` with explicit types. All timestamps are UTC `DateTime`. All IDs are auto-incrementing integers. All version references are immutable after creation.

### 3.1 EvaluationDefinition

```
Table: evaluation_definitions

id                  Integer, PK, autoincrement
name                String(200), not null, unique
description         Text, nullable
owner               String(100), nullable
tags                Text, nullable                  -- JSON array of strings
suite_name          String(200), nullable           -- optional grouping
execution_mode      String(50), not null, default="sequential"  -- sequential | parallel | matrix
created_at          DateTime, server_default=now()
updated_at          DateTime, onupdate=now()
is_archived         Boolean, default=False

Relationships:
  versions          → EvaluationVersion (one-to-many, cascade delete)
```

### 3.2 EvaluationVersion

An immutable snapshot of an evaluation definition at a point in time. Any change to bindings, thresholds, or preprocessing creates a new version.

```
Table: evaluation_versions

id                  Integer, PK, autoincrement
evaluation_id       Integer, FK → evaluation_definitions.id, not null
version_number      Integer, not null
dataset_version_id  Integer, FK → dataset_versions.id, not null
scorer_config       Text, not null                  -- JSON: list of {scorer_version_id, weight, pass_threshold}
prompt_template     Text, nullable                  -- harness-level prompt template, if any
preprocessing       Text, nullable                  -- JSON: preprocessing steps
pass_criteria       Text, nullable                  -- JSON: overall pass/fail rules
notes               Text, nullable
created_at          DateTime, server_default=now()

Unique constraint: (evaluation_id, version_number)

Relationships:
  evaluation        → EvaluationDefinition (many-to-one)
  dataset_version   → DatasetVersion (many-to-one)
  runs              → Run (one-to-many)
```

### 3.3 Dataset

```
Table: datasets

id                  Integer, PK, autoincrement
name                String(200), not null, unique
description         Text, nullable
source              String(100), nullable           -- "manual", "imported", "generated"
tags                Text, nullable                  -- JSON array
created_at          DateTime, server_default=now()
is_archived         Boolean, default=False

Relationships:
  versions          → DatasetVersion (one-to-many, cascade delete)
```

### 3.4 DatasetVersion

```
Table: dataset_versions

id                  Integer, PK, autoincrement
dataset_id          Integer, FK → datasets.id, not null
version_number      Integer, not null
item_count          Integer, not null, default=0
checksum            String(64), nullable            -- SHA-256 of serialized items
notes               Text, nullable
created_at          DateTime, server_default=now()

Unique constraint: (dataset_id, version_number)

Relationships:
  dataset           → Dataset (many-to-one)
  test_cases        → TestCase (one-to-many, cascade delete)
```

### 3.5 TestCase

```
Table: test_cases

id                  Integer, PK, autoincrement
dataset_version_id  Integer, FK → dataset_versions.id, not null
item_index          Integer, not null               -- ordering within dataset
input_text          Text, not null                  -- the prompt / input
expected_output     Text, nullable                  -- gold answer, if any
context             Text, nullable                  -- additional context for the model
metadata            Text, nullable                  -- JSON: task_family, difficulty, modality, tags, token_estimate
created_at          DateTime, server_default=now()

Index: (dataset_version_id, item_index)
```

### 3.6 Scorer

```
Table: scorers

id                  Integer, PK, autoincrement
name                String(200), not null, unique
scorer_type         String(50), not null            -- exact_match, fuzzy_match, rubric, format_validator,
                                                    -- structured_output, latency_cost, safety, model_judge, aggregate
description         Text, nullable
tags                Text, nullable                  -- JSON array
created_at          DateTime, server_default=now()
is_archived         Boolean, default=False

Relationships:
  versions          → ScorerVersion (one-to-many, cascade delete)
```

### 3.7 ScorerVersion

```
Table: scorer_versions

id                  Integer, PK, autoincrement
scorer_id           Integer, FK → scorers.id, not null
version_number      Integer, not null
config              Text, not null                  -- JSON: all scorer parameters
                                                    -- For model_judge: {judge_model, judge_endpoint, judge_params}
                                                    -- For rubric: {rubric_text, scale_min, scale_max, pass_threshold}
                                                    -- For exact_match: {case_sensitive, strip_whitespace, normalize}
                                                    -- For latency_cost: {latency_threshold_ms, cost_threshold_usd}
implementation_ref  String(500), nullable           -- module path or callable reference (e.g., "ai_benchmark.eval.scoring.builtin.exact_match:ExactMatchScorer")
notes               Text, nullable
created_at          DateTime, server_default=now()

Unique constraint: (scorer_id, version_number)
```

### 3.8 TargetConfiguration

```
Table: target_configurations

id                  Integer, PK, autoincrement
name                String(200), not null, unique   -- human label, e.g., "DGX Spark / GLM-4.7 / long context"
model_name          String(200), not null           -- model identifier (e.g., "gpt-4o", "qwen2.5-7b-instruct")
model_family        String(100), nullable           -- grouping (e.g., "GPT", "Qwen", "Llama")
provider            String(100), not null           -- "openai", "anthropic", "local_ollama", "local_vllm", "local_llamacpp", "generic_http"
endpoint_url        String(500), nullable           -- API URL or local server address
machine_profile_id  Integer, FK → machine_profiles.id, nullable
runtime_backend     String(100), nullable           -- "ollama", "vllm", "llama.cpp", "exllamav2", "tgi", "cloud_api"
prompt_wrapper      Text, nullable                  -- system prompt or prompt template override
inference_params    Text, not null                  -- JSON: {temperature, top_p, max_tokens, stop_sequences, ...}
runtime_options     Text, nullable                  -- JSON: {quantization, gpu_layers, batch_size, context_size, ...}
tags                Text, nullable                  -- JSON array
notes               Text, nullable
created_at          DateTime, server_default=now()
updated_at          DateTime, onupdate=now()
is_archived         Boolean, default=False

Relationships:
  machine_profile   → MachineProfile (many-to-one)
  runs              → Run (one-to-many)
```

### 3.9 MachineProfile

```
Table: machine_profiles

id                  Integer, PK, autoincrement
hostname            String(200), not null, unique
display_name        String(200), nullable           -- e.g., "DGX Spark", "RTX 4070 Workstation"
hardware_class      String(100), not null           -- "dgx_spark", "rtx_4070_workstation", "macbook_pro_m4",
                                                    -- "mac_mini_m4", "standard_laptop", "gtx_1060_laptop", "edge_accelerator"
cpu_description     String(200), nullable
gpu_description     String(200), nullable           -- e.g., "NVIDIA RTX 4070 12GB", "Apple M4 Pro 20-core GPU"
accelerator_details Text, nullable                  -- JSON: {vram_gb, cuda_cores, tensor_cores, compute_capability, ...}
ram_gb              Integer, nullable
storage_summary     String(200), nullable
os_description      String(200), nullable
runtime_availability Text, nullable                 -- JSON: list of available runtimes ["ollama", "vllm", ...]
capacity_notes      Text, nullable                  -- free-form notes on what the machine can handle
created_at          DateTime, server_default=now()
updated_at          DateTime, onupdate=now()

Relationships:
  snapshots         → MachineSnapshot (one-to-many)
  target_configs    → TargetConfiguration (one-to-many)
```

### 3.10 MachineSnapshot

Immutable capture of machine state at the time of a run. Stored as a copy, not a reference, so the run record remains valid even if the profile is later updated.

```
Table: machine_snapshots

id                  Integer, PK, autoincrement
machine_profile_id  Integer, FK → machine_profiles.id, not null
snapshot_data       Text, not null                  -- JSON: full copy of MachineProfile fields at capture time
                                                    -- plus runtime_version, model_server_version, env_vars, tuning_values
captured_at         DateTime, server_default=now()
```

### 3.11 Run

```
Table: runs

id                  Integer, PK, autoincrement
run_group_id        Integer, FK → run_groups.id, nullable  -- null for standalone runs
evaluation_version_id Integer, FK → evaluation_versions.id, not null
target_config_id    Integer, FK → target_configurations.id, not null
machine_snapshot_id Integer, FK → machine_snapshots.id, nullable
dataset_version_id  Integer, FK → dataset_versions.id, not null  -- denormalized for fast query

status              String(30), not null, default="queued"
                    -- queued | provisioning | running | scoring | completed | failed | canceled | partially_completed
trigger_type        String(30), not null, default="manual"  -- manual | scheduled | api | matrix
priority            Integer, default=0

started_at          DateTime, nullable
scoring_started_at  DateTime, nullable
completed_at        DateTime, nullable
error_message       Text, nullable

total_items         Integer, not null, default=0
completed_items     Integer, not null, default=0
failed_items        Integer, not null, default=0
skipped_items       Integer, not null, default=0

created_at          DateTime, server_default=now()
updated_at          DateTime, onupdate=now()

Relationships:
  run_group         → RunGroup (many-to-one)
  evaluation_version → EvaluationVersion (many-to-one)
  target_config     → TargetConfiguration (many-to-one)
  machine_snapshot  → MachineSnapshot (many-to-one)
  item_results      → RunItemResult (one-to-many, cascade delete)
  aggregate_metrics → RunAggregateMetric (one-to-many, cascade delete)
  artifacts         → Artifact (one-to-many, cascade delete)
```

### 3.12 RunGroup

Groups related runs from a matrix or batch execution.

```
Table: run_groups

id                  Integer, PK, autoincrement
name                String(200), nullable
description         Text, nullable
execution_type      String(30), not null            -- batch | matrix
created_at          DateTime, server_default=now()

Relationships:
  runs              → Run (one-to-many)
```

### 3.13 RunItemResult

```
Table: run_item_results

id                  Integer, PK, autoincrement
run_id              Integer, FK → runs.id, not null
test_case_id        Integer, FK → test_cases.id, not null
item_index          Integer, not null

input_sent          Text, not null                  -- actual prompt sent (after template application)
raw_output          Text, nullable                  -- raw model response
normalized_output   Text, nullable                  -- post-processed output, if applicable
scorer_results      Text, not null                  -- JSON: list of {scorer_version_id, score, pass, details}
overall_pass        Boolean, nullable
error_message       Text, nullable

latency_ms          Float, nullable
prompt_tokens       Integer, nullable
completion_tokens   Integer, nullable
total_tokens        Integer, nullable
cost_estimate_usd   Float, nullable
retry_count         Integer, default=0
trace_id            String(200), nullable           -- external trace/span ID if available

started_at          DateTime, nullable
completed_at        DateTime, nullable

Index: (run_id, item_index)
Index: (run_id, overall_pass)

Relationships:
  run               → Run (many-to-one)
  test_case         → TestCase (many-to-one)
```

### 3.14 RunAggregateMetric

```
Table: run_aggregate_metrics

id                  Integer, PK, autoincrement
run_id              Integer, FK → runs.id, not null
metric_name         String(200), not null           -- e.g., "overall_accuracy", "avg_latency_ms", "total_cost_usd",
                                                    -- "scorer:exact_match:pass_rate", "scorer:rubric:avg_score"
metric_value        Float, not null
metric_metadata     Text, nullable                  -- JSON: {count, std_dev, min, max, percentiles, ...}
created_at          DateTime, server_default=now()

Unique constraint: (run_id, metric_name)
```

### 3.15 Artifact

```
Table: artifacts

id                  Integer, PK, autoincrement
run_id              Integer, FK → runs.id, not null
artifact_type       String(50), not null            -- result_table | log | json_export | csv_export | html_report | plot | raw_bundle
filename            String(500), not null
file_path           String(1000), not null          -- path on disk or object store key
size_bytes          Integer, nullable
mime_type           String(100), nullable
created_at          DateTime, server_default=now()
```

---

## 4. API Specification

Base path: `/api/eval`

All endpoints return JSON. All list endpoints support `?limit=N&offset=M&sort=field&order=asc|desc`. All create/update endpoints accept JSON bodies. Errors return `{"detail": "..."}` with appropriate HTTP status codes.

### 4.1 Evaluations

| Method | Path | Description |
|---|---|---|
| GET | `/evaluations` | List evaluation definitions. Filters: `?name=`, `?tags=`, `?archived=` |
| POST | `/evaluations` | Create evaluation definition. Body: `{name, description, owner, tags, suite_name, execution_mode}` |
| GET | `/evaluations/{id}` | Get evaluation definition with version list |
| PUT | `/evaluations/{id}` | Update mutable fields (name, description, tags, is_archived) |
| POST | `/evaluations/{id}/versions` | Create new version. Body: `{dataset_version_id, scorer_config, prompt_template, preprocessing, pass_criteria, notes}` |
| GET | `/evaluations/{id}/versions/{version}` | Get specific version |

### 4.2 Datasets

| Method | Path | Description |
|---|---|---|
| GET | `/datasets` | List datasets. Filters: `?name=`, `?source=`, `?tags=` |
| POST | `/datasets` | Create dataset. Body: `{name, description, source, tags}` |
| GET | `/datasets/{id}` | Get dataset with version list |
| POST | `/datasets/{id}/versions` | Create dataset version. Body: `{notes, items: [{input_text, expected_output, context, metadata}]}` |
| GET | `/datasets/{id}/versions/{version}` | Get version with item count |
| GET | `/datasets/{id}/versions/{version}/items` | List test cases. Filters: `?tag=`, `?difficulty=`, `?modality=`. Supports `?limit=&offset=` |
| POST | `/datasets/{id}/versions/{version}/items/filter` | Filter items by metadata query. Body: `{tags, min_tokens, max_tokens, modalities, task_families}`. Returns filtered item IDs. |

### 4.3 Scorers

| Method | Path | Description |
|---|---|---|
| GET | `/scorers` | List scorers. Filters: `?type=`, `?name=` |
| POST | `/scorers` | Create scorer. Body: `{name, scorer_type, description, tags}` |
| GET | `/scorers/{id}` | Get scorer with version list |
| POST | `/scorers/{id}/versions` | Create version. Body: `{config, implementation_ref, notes}` |

### 4.4 Target Configurations

| Method | Path | Description |
|---|---|---|
| GET | `/targets` | List targets. Filters: `?model_name=`, `?provider=`, `?machine=`, `?hardware_class=`, `?archived=` |
| POST | `/targets` | Create target. Body: all TargetConfiguration fields |
| GET | `/targets/{id}` | Get target detail |
| PUT | `/targets/{id}` | Update target |
| POST | `/targets/{id}/clone` | Clone target. Body: `{name, overrides: {field: value}}`. Returns new target with one or more fields changed. |

### 4.5 Machines

| Method | Path | Description |
|---|---|---|
| GET | `/machines` | List machine profiles. Filters: `?hardware_class=`, `?hostname=` |
| POST | `/machines` | Create machine profile. Body: all MachineProfile fields |
| GET | `/machines/{id}` | Get machine profile |
| PUT | `/machines/{id}` | Update machine profile |
| POST | `/machines/{id}/snapshot` | Capture current machine state. Body: `{runtime_version, model_server_version, env_vars, tuning_values}`. Returns MachineSnapshot. |

### 4.6 Runs

| Method | Path | Description |
|---|---|---|
| GET | `/runs` | List runs. Filters: `?evaluation_id=`, `?target_id=`, `?machine_id=`, `?status=`, `?model_name=`, `?hardware_class=`, `?date_from=`, `?date_to=`, `?tags=` |
| POST | `/runs` | Create and queue a single run. Body: `{evaluation_version_id, target_config_id, trigger_type, priority}` |
| POST | `/runs/batch` | Create a batch/matrix of runs. Body: `{evaluation_version_id, target_config_ids: [int], execution_type, name}`. Returns RunGroup with child Run IDs. |
| GET | `/runs/{id}` | Get run detail with aggregate metrics |
| GET | `/runs/{id}/items` | List item results. Filters: `?pass=`, `?scorer=`, `?min_latency=`. Supports `?limit=&offset=` |
| GET | `/runs/{id}/items/{item_id}` | Get single item result detail |
| GET | `/runs/{id}/metrics` | Get all aggregate metrics for this run |
| GET | `/runs/{id}/artifacts` | List artifacts for this run |
| GET | `/runs/{id}/artifacts/{artifact_id}/download` | Download artifact file |
| POST | `/runs/{id}/cancel` | Cancel a queued or running run |
| POST | `/runs/{id}/retry` | Retry failed items only. Creates new item results, preserves existing passes. |
| POST | `/runs/{id}/rescore` | Re-run scoring on stored outputs with a new scorer config. Body: `{scorer_config}`. Does not re-run generation. |

### 4.7 Comparisons

| Method | Path | Description |
|---|---|---|
| POST | `/comparisons` | Compare runs. Body: `{run_ids: [int]}`. Returns comparison result with per-metric deltas, per-scorer breakdown, per-item diffs. |
| POST | `/comparisons/config-diff` | Diff target configs. Body: `{target_ids: [int]}`. Returns field-level differences. |

### 4.8 Reports

| Method | Path | Description |
|---|---|---|
| POST | `/reports/summary` | Generate summary report. Body: `{group_by, filters, metrics, format}`. `group_by`: "evaluation", "model_family", "machine", "date_range". `format`: "json", "csv", "html". |
| GET | `/reports/presets` | List saved report presets |
| POST | `/reports/presets` | Save a preset. Body: `{name, config}` |
| GET | `/reports/presets/{id}/run` | Execute a saved preset |

---

## 5. Execution Engine

### 5.1 Orchestrator Flow

```
User triggers run (UI / CLI / API)
    │
    ▼
orchestrator.create_run()
    → Validate evaluation_version, target_config, dataset_version exist
    → Capture machine_snapshot if machine_profile_id is set
    → Create Run record with status="queued"
    → Enqueue execution job
    │
    ▼
orchestrator.execute_run(run_id)
    → Set status="running", started_at=now()
    → Load dataset items (optionally filtered)
    → For each item (sequential or parallel per execution_mode):
        │
        ├── executor.execute_item(item, target_config)
        │     → Resolve adapter from target_config.provider
        │     → Apply prompt_wrapper / prompt_template
        │     → Call adapter.generate(prompt, inference_params)
        │     → Capture: raw_output, latency_ms, tokens, cost, trace_id, retry_count
        │     → Store RunItemResult with status fields
        │     → Update run.completed_items counter
        │
        └── On error: store error in RunItemResult, increment run.failed_items, continue
    │
    ▼
orchestrator.score_run(run_id)
    → Set status="scoring", scoring_started_at=now()
    → Load scorer_config from evaluation_version
    → For each RunItemResult:
        → For each scorer in scorer_config:
            → scorer_runner.score(item_result, scorer_version, test_case)
            → Append to item_result.scorer_results JSON
            → Compute item_result.overall_pass
    → Compute RunAggregateMetric rows (pass_rate, avg_score per scorer, avg_latency, total_cost, etc.)
    │
    ▼
orchestrator.finalize_run(run_id)
    → Set status="completed" (or "partially_completed" if failed_items > 0)
    → Set completed_at=now()
    → Generate default artifacts (result table JSON, summary CSV)
```

### 5.2 Model Adapter Interface

```python
class ModelAdapter(ABC):
    """Abstract interface for calling a model endpoint."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        inference_params: dict,       # {temperature, top_p, max_tokens, stop, ...}
        runtime_options: dict | None, # {timeout, retries, ...}
    ) -> GenerationResult:
        """Send prompt, return result."""
        ...

@dataclass
class GenerationResult:
    output_text: str
    raw_response: dict | None = None  # full API response for debugging
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate_usd: float | None = None
    trace_id: str | None = None
    retry_count: int = 0
    error: str | None = None
```

**Required adapter implementations (initial release):**

| Adapter | Provider value | Endpoint |
|---|---|---|
| `OpenAIAdapter` | `openai` | OpenAI-compatible chat completions API |
| `AnthropicAdapter` | `anthropic` | Anthropic messages API |
| `LocalAdapter` | `local_ollama`, `local_vllm`, `local_llamacpp` | Local HTTP server (OpenAI-compatible format) |
| `GenericHTTPAdapter` | `generic_http` | User-specified URL with configurable request/response mapping |

### 5.3 Scorer Interface

```python
class BaseScorer(ABC):
    """Abstract interface for scoring a single item."""

    @abstractmethod
    def score(
        self,
        input_text: str,
        expected_output: str | None,
        actual_output: str,
        context: str | None,
        config: dict,
    ) -> ScorerResult:
        ...

@dataclass
class ScorerResult:
    score: float                    # numeric score
    passed: bool                    # pass/fail against threshold
    details: dict | None = None     # scorer-specific details (e.g., rubric dimension scores)
```

**Required scorer implementations (initial release):**

| Scorer | Type | Config keys |
|---|---|---|
| `ExactMatchScorer` | `exact_match` | `case_sensitive`, `strip_whitespace`, `normalize_unicode` |
| `FuzzyMatchScorer` | `fuzzy_match` | `threshold` (0.0–1.0), `method` ("levenshtein", "token_overlap") |
| `RubricScorer` | `rubric` | `rubric_text`, `scale_min`, `scale_max`, `pass_threshold` |
| `FormatValidatorScorer` | `format_validator` | `expected_format` ("json", "xml", "markdown", "code"), `schema` (optional JSON schema) |
| `LatencyCostScorer` | `latency_cost` | `latency_threshold_ms`, `cost_threshold_usd`, `token_budget` |
| `SafetyScorer` | `safety` | `categories` (list of safety categories to check), `threshold` |
| `ModelJudgeScorer` | `model_judge` | `judge_model`, `judge_endpoint`, `judge_params`, `judge_prompt_template`, `scale_min`, `scale_max`, `pass_threshold` |

---

## 6. CLI Commands

Added as a subgroup under the existing `ai-benchmark` CLI.

```
ai-benchmark eval run           --evaluation <name_or_id> --target <name_or_id> [--priority N]
ai-benchmark eval run-matrix    --evaluation <name_or_id> --targets <id,id,id> [--name "matrix name"]
ai-benchmark eval status        [--run-id N] [--active] [--recent N]
ai-benchmark eval list          [--evaluations] [--datasets] [--scorers] [--targets] [--machines]
ai-benchmark eval compare       --runs <id,id> [--format json|csv|text]
ai-benchmark eval export        --run <id> --format <json|csv|html> [--output path]
ai-benchmark eval rescore       --run <id> --scorer-config <json_path>
ai-benchmark eval serve         [--host 0.0.0.0] [--port 8080]   # start the UI + API server
```

---

## 7. UI Page Specifications

### 7.1 Top-Level Navigation

Sidebar or top-nav with: **Dashboard** | **Evaluations** | **Datasets** | **Scorers** | **Targets** | **Machines** | **Runs** | **Reports**

Dashboard shows: active runs with progress bars, recent completions, failure alerts, machine utilization.

### 7.2 Evaluation List Page

- Table: name, latest version, dataset, scorer count, last run date, run count, tags
- Actions: create new, archive, view detail
- Click row → evaluation detail page

### 7.3 Evaluation Detail Page

- Header: name, description, owner, suite, tags
- Version history table: version number, dataset version, scorer config summary, created date
- Right panel: "New Run" button → run trigger form
- Bottom: recent runs for this evaluation

### 7.4 Target Configuration List Page

- Table: name, model, provider, machine, runtime, quantization, key params
- Highlight config differences when multiple rows selected
- Actions: create, clone, archive
- Diff view: select 2+ targets → show field-level differences side by side

### 7.5 Run List Page

- Table: run ID, evaluation name, target name, machine, status, progress, started, duration, pass rate, avg latency
- Filters: status, evaluation, target, machine, hardware class, date range, model family
- Sortable by any metric column
- Checkbox select → "Compare Selected" button

### 7.6 Run Detail Page

- Header: status badge, evaluation name + version, target name, machine, trigger type
- Summary cards: total items, pass rate, avg score, avg latency, total cost, failed count
- Tabs:
  - **Results**: paginated table of item results (input preview, output preview, pass/fail, score, latency)
  - **Scorer Breakdown**: per-scorer pass rate, score distribution, worst items per scorer
  - **Configuration**: full target config, machine snapshot, inference params, runtime options
  - **Artifacts**: downloadable files (result tables, exports, logs)
  - **Traces**: trace IDs with links (if external tracing configured)
- Click any item row → item detail modal (full input, full output, all scorer results, raw response)

### 7.7 Live Run Page

- Same as run detail but with auto-refresh
- Progress bar with item count
- Streaming table of completed items as they arrive
- Elapsed time, estimated remaining

### 7.8 Comparison Page

- Triggered from run list (select 2+) or from API
- Layout: columns per run, rows per metric
- Section 1: **Aggregate comparison** — metric table with delta columns and win/loss highlighting
- Section 2: **Scorer comparison** — per-scorer pass rate and avg score side by side
- Section 3: **Item comparison** — aligned table showing each item's output and scores across runs, with diff highlighting for output text
- Section 4: **Config diff** — side-by-side target config, highlighting fields that differ
- Filter: show only items where runs disagree, show only failures, show only items above latency threshold

### 7.9 Reports / Dashboard Page

- Preset reports: "Best Coding Runs", "Quantization Comparison", "Standard Laptop Viability", "Older Hardware Baseline"
- Custom report builder: select group_by, filters, metrics, date range
- Charts: bar chart of pass rate by model, scatter plot of quality vs latency, trend line over time
- Export: JSON, CSV, HTML

---

## 8. Database Migrations

Create a single Alembic migration for all evaluation tables. Migration file: `alembic/versions/002_evaluation_pipeline.py`

Tables to create (in dependency order):
1. `datasets`
2. `dataset_versions`
3. `test_cases`
4. `scorers`
5. `scorer_versions`
6. `evaluation_definitions`
7. `evaluation_versions`
8. `machine_profiles`
9. `machine_snapshots`
10. `target_configurations`
11. `run_groups`
12. `runs`
13. `run_item_results`
14. `run_aggregate_metrics`
15. `artifacts`

---

## 9. Configuration

Add to `ai_benchmark/config/settings.py` or create `ai_benchmark/eval/config.py`:

```python
class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_BENCH_EVAL_")

    api_host: str = "127.0.0.1"
    api_port: int = 8080
    artifact_storage_path: str = "./artifacts"
    max_concurrent_items: int = 10          # parallel item execution within a run
    default_execution_mode: str = "sequential"
    run_timeout_seconds: int = 3600         # 1 hour per run
    item_timeout_seconds: int = 120         # 2 min per item
    retry_failed_items: int = 2             # auto-retries per item
    enable_cost_tracking: bool = True
    local_only_mode: bool = False           # when true, refuse to send to remote endpoints
```

---

## 10. Testing Requirements

### 10.1 Unit Tests

| Test file | Coverage |
|---|---|
| `test_eval_models.py` | Create all 15 tables, insert/query each entity, verify FK constraints, unique constraints, and JSON field round-trips |
| `test_dataset_service.py` | Dataset + version CRUD, test case insertion, filtering by metadata tags |
| `test_scorer_runner.py` | Each built-in scorer: exact match, fuzzy match, rubric, format validator, latency/cost, model judge (mocked) |
| `test_orchestrator.py` | Full run lifecycle: queued → running → scoring → completed. Partial failure handling. Matrix run creation. |
| `test_executor.py` | Adapter resolution, prompt template application, mock model calls, error capture |
| `test_comparison_service.py` | Two-run and three-run comparison, metric deltas, item-level diff generation, config diff |

### 10.2 API Tests

| Test file | Coverage |
|---|---|
| `test_evaluations_api.py` | CRUD endpoints, version creation, validation errors |
| `test_runs_api.py` | Run creation, batch creation, status transitions, item listing, cancel, retry, rescore |
| `test_comparisons_api.py` | Comparison endpoint, config diff endpoint |

### 10.3 Integration Tests

| Test | Description |
|---|---|
| End-to-end smoke test | Create evaluation + dataset + scorer + target + machine → trigger run → wait for completion → verify item results + aggregate metrics → compare with second run |
| CLI smoke test | `eval run`, `eval status`, `eval compare`, `eval export` against test database |
| Rescore test | Complete a run, change scorer config, rescore, verify new scores without re-running generation |

---

## 11. Acceptance Criteria (Verifiable)

| # | Criterion | How to verify |
|---|---|---|
| AC-1 | Define one evaluation, bind dataset + scorer, run against 3+ targets | `POST /evaluations`, `POST /evaluations/{id}/versions`, `POST /runs/batch` with 3 target IDs → 3 runs created |
| AC-2 | Side-by-side comparison shows metric deltas, scorer breakdown, item diffs, config diffs | `POST /comparisons` with 2 run IDs → response contains all 4 sections |
| AC-3 | Historical run fully inspectable after 6+ weeks | Query run by ID → response includes evaluation version, dataset version, scorer versions, target config, machine snapshot |
| AC-4 | Runs launchable from CLI and API without UI | `ai-benchmark eval run --evaluation X --target Y` → creates and executes run |
| AC-5 | Filter runs by machine class | `GET /runs?hardware_class=standard_laptop` → returns only matching runs |
| AC-6 | Active vs historical clearly separated | Dashboard API returns `{active_runs: [...], recent_completed: [...]}` with distinct status groups |
| AC-7 | Rescore without re-running generation | `POST /runs/{id}/rescore` with new scorer config → new scorer results on same stored outputs |
| AC-8 | Partial failure preserved | Run with 1 failed item out of 10 → status="partially_completed", 9 item results visible, 1 error captured |

---

## 12. Implementation Phases (Suggested)

| Phase | Scope | Depends on |
|---|---|---|
| E1 | Data models (all 15 tables), Alembic migration, model unit tests | Existing Phase 1 infra |
| E2 | Service layer (CRUD for all entities), dataset/scorer versioning | E1 |
| E3 | Execution engine: orchestrator, executor, 4 model adapters, GenerationResult | E2 |
| E4 | Scoring engine: scorer_runner + 7 built-in scorers, aggregate metric computation | E3 |
| E5 | FastAPI routes (all endpoints from Section 4), Pydantic schemas, API tests | E2 (can parallel E3/E4 for non-run endpoints) |
| E6 | CLI commands (`eval run`, `eval status`, `eval compare`, `eval export`, `eval serve`) | E3, E4, E5 |
| E7 | UI templates: dashboard, evaluation pages, target pages, run pages | E5 |
| E8 | Comparison UI + report builder + saved presets | E5, E7 |
| E9 | Integration tests, end-to-end smoke tests, acceptance criteria verification | All prior |
