# Eval Automation Payload Examples

Machine-readable inputs for the evaluation pipeline API, suitable for automation
scripts and Claude Code skill invocations.

## Single Run Launch

```json
{
  "evaluation_version_id": 1,
  "target_config_id": 3,
  "trigger_type": "api",
  "priority": 0,
  "machine_profile_id": 2
}
```

POST to `/api/eval/runs`

## Matrix Run Launch (Batch)

```json
{
  "evaluation_version_id": 1,
  "target_config_ids": [3, 4, 5, 6],
  "execution_type": "matrix",
  "name": "Runner Comparison: Llama-3 70B across all runners",
  "machine_profile_id": 1
}
```

POST to `/api/eval/runs/batch`

## Rescore with New Config

```json
{
  "scorer_config": [
    {
      "scorer_version_id": 2,
      "weight": 1.0,
      "pass_threshold": 0.7
    },
    {
      "scorer_version_id": 5,
      "weight": 0.5,
      "pass_threshold": 0.3
    }
  ]
}
```

POST to `/api/eval/runs/{run_id}/rescore`

## Scheduled Execution (Nightly Regression)

Create a run group with `scheduled_at` and use an external cron or scheduler:

```bash
# Cron entry: every night at 2am
0 2 * * * curl -X POST http://localhost:8100/api/eval/runs/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AI_BENCH_EVAL_API_KEY" \
  -d '{
    "evaluation_version_id": 1,
    "target_config_ids": [3, 4],
    "execution_type": "scheduled",
    "name": "Nightly regression"
  }'
```

## Runner Comparison Preset Payload

```json
{
  "evaluation_version_id": 1,
  "target_config_ids": [10, 11, 12, 13, 14, 15, 16, 17],
  "execution_type": "matrix",
  "name": "Full Runner Comparison: 8 runners on DGX Spark"
}
```

Each target config points to the same model but uses a different runner
(ollama, lmstudio, llamacpp, mlx, vllm, sglang, tensorrt, openvino).

## Machine Comparison Preset Payload

```json
{
  "evaluation_version_id": 1,
  "target_config_ids": [20, 21, 22, 23, 24, 25, 26],
  "execution_type": "matrix",
  "name": "Machine Comparison: Ollama on all 7 machines"
}
```

Each target config points to the same model + runner but different machines.

## CLI Equivalents

```bash
# Single run
ai-benchmark eval run --evaluation "coding-bench" --target "ollama-dgx"

# Matrix run
ai-benchmark eval run-matrix --evaluation "coding-bench" \
  --targets 10,11,12,13,14,15,16,17

# Check status
ai-benchmark eval status --run 42

# Export results
ai-benchmark eval export --run 42 --format json --output results.json

# Rescore
ai-benchmark eval rescore --run 42 --scorer-config new_scorers.json

# List runners
ai-benchmark eval runners
ai-benchmark eval runners --id 3

# List machines
ai-benchmark eval machines --hardware-class dgx_spark
```

## Authentication

When `AI_BENCH_EVAL_API_KEY` is set, include the key in requests:

```bash
# Via header
curl -H "X-API-Key: your-key-here" http://localhost:8100/api/eval/runs

# Via Bearer token
curl -H "Authorization: Bearer your-key-here" http://localhost:8100/api/eval/runs
```

When the env var is not set, authentication is disabled (lab/local mode).
