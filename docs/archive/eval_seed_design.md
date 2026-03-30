# Eval Pipeline Seed Data Design Document

## 1. Purpose

The eval pipeline's runs/launch page (`/eval/runs/launch`) is currently unusable because the Evaluation dropdown and Target checkboxes are empty. No evaluation definitions, datasets, scorers, or target configurations exist in the database. This document defines the seed data needed to make the eval pipeline functional out of the box.

## 2. Scope

The existing seed service (`ai_benchmark/eval/services/seed.py`) seeds 8 runner profiles and 7 machine profiles. This work extends seeding to cover the remaining four entity families required by the launch page:

1. **Scorers** — Register the 7 built-in scorers with default-config versions
2. **Datasets** — Create representative evaluation datasets with test cases
3. **Evaluation definitions** — Wire datasets to scorer configs via evaluation versions
4. **Target configurations** — Define model targets linked to existing runners and machines

Additionally, the `run_launch_submit` route has a hardcoded `evaluation_version_id=1` that must be replaced with the form-selected evaluation.

## 3. Core Design Principles

1. **Extend, don't replace** — Follow the identical pattern in `seed.py`: define seed data as module-level dicts, write `seed_<entity>(session)` functions that skip duplicates by unique field, and wire into `seed_all()`.

2. **Dependency order** — Entities must be seeded in dependency order: scorers → datasets → evaluations (which reference scorer versions and dataset versions) → targets (which reference runners and machines). Runners and machines are already seeded first.

3. **Realistic but minimal** — Seed enough data to make the launch page functional and demonstrate the system's capabilities, but don't create an exhaustive catalog. 7 scorers, 3 datasets (~10 test cases each), 4 evaluation definitions, 6 target configurations.

4. **Idempotent** — Every seed function checks for existing records by unique name/key before inserting. Running `seed_all()` twice produces no duplicates.

## 4. Primary User Stories

1. As a user visiting `/eval/runs/launch`, I can select an evaluation from the dropdown and check one or more targets, then launch a run.

2. As a developer setting up the system, I can run `ai-benchmark eval seed` to populate the eval pipeline with working seed data.

3. As a user exploring the eval UI, I can see evaluations, datasets, scorers, and targets in their respective list pages, giving me examples of how the system is structured.

## 5. Functional Requirements

### 5.1 Scorer Seeds

Register all 7 built-in scorers with one ScorerVersion each using their default configurations.

| Scorer Name | Type | Default Config |
|---|---|---|
| Exact Match | exact_match | `{"strip_whitespace": true, "case_sensitive": true}` |
| Fuzzy Match | fuzzy_match | `{"threshold": 0.85, "case_sensitive": false}` |
| Format Validator | format_validator | `{"expected_format": "json"}` |
| Latency & Cost | latency_cost | `{}` |
| Model Judge | model_judge | `{"judge_provider": "openai", "scale_max": 5, "pass_threshold": 3}` |
| Rubric | rubric | `{"scale_max": 5, "pass_threshold": 3}` |
| Safety | safety | `{"categories": ["violence", "hate_speech", "self_harm", "illegal_activity", "sexual_content"]}` |

Each scorer gets version 1 with notes indicating it is the built-in default.

### 5.2 Dataset Seeds

Create 3 representative datasets covering distinct evaluation scenarios:

**Dataset 1: General Knowledge QA** — Short factual questions with exact answers. Tests basic model accuracy.
- 10 test cases (factual Q&A pairs)
- Scored by: exact_match

**Dataset 2: Reasoning & Math** — Multi-step reasoning and math word problems. Tests chain-of-thought.
- 10 test cases (math/logic problems with numeric answers)
- Scored by: exact_match, rubric

**Dataset 3: Instruction Following** — Tasks that test format compliance and safety. Tests model alignment.
- 10 test cases (format-constrained prompts)
- Scored by: format_validator, safety

Each dataset gets one DatasetVersion (version 1) with accurate `item_count` and test cases with `item_index`, `input_text`, `expected_output`, and `metadata_json` (task_family, difficulty).

### 5.3 Evaluation Definition Seeds

Create 4 evaluation definitions that combine datasets with scorer configurations:

| Evaluation | Dataset | Scorers (weight) | Mode |
|---|---|---|---|
| General Knowledge v1 | General Knowledge QA | exact_match (1.0) | sequential |
| Reasoning Accuracy v1 | Reasoning & Math | exact_match (0.6), rubric (0.4) | sequential |
| Instruction Compliance v1 | Instruction Following | format_validator (0.5), safety (0.5) | sequential |
| Full Suite v1 | General Knowledge QA | exact_match (0.7), fuzzy_match (0.3) | parallel |

Each evaluation definition gets one EvaluationVersion (version 1) linking to the appropriate `dataset_version_id` and `scorer_config` (JSON list of `{scorer_version_id, weight, pass_threshold}`).

### 5.4 Target Configuration Seeds

Create 6 target configurations spanning cloud API and local inference:

| Target Name | Provider | Model | Runner | Machine |
|---|---|---|---|---|
| GPT-4o (OpenAI API) | openai | gpt-4o | — | — |
| Claude Sonnet (Anthropic API) | anthropic | claude-sonnet-4-20250514 | — | — |
| Llama 3.1 8B (Ollama) | ollama | llama3.1:8b | ollama-default | mbp-m4-64 |
| Llama 3.1 8B (LM Studio) | lmstudio | llama-3.1-8b | lmstudio-default | mbp-m4-64 |
| Phi-3 Mini (llama.cpp) | llamacpp | phi-3-mini-4k | llamacpp-default | mac-mini-m4-24 |
| Qwen2.5 7B (vLLM) | vllm | qwen2.5-7b | vllm-default | rtx4070-desktop |

Cloud targets (OpenAI, Anthropic) have no runner or machine — they use external APIs. Local targets link to existing runner and machine profiles.

### 5.5 Launch Route Bug Fix

Replace the hardcoded `evaluation_version_id=1` in `run_launch_submit` (server.py ~line 702) with the form-submitted `evaluation_id`. The route must:
1. Read `evaluation_id` from the form
2. Query the latest EvaluationVersion for that evaluation
3. Use its `id` as `evaluation_version_id` when creating the run

### 5.6 CLI Command

Add `ai-benchmark eval seed` subcommand that:
1. Calls `seed_all(session)` (which now includes all entity families)
2. Prints a summary of what was created vs. skipped
3. Is idempotent — safe to run repeatedly
