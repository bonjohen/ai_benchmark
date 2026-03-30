# Eval Pipeline Seed Data — Implementation Plan

**Source document:** `docs/eval_seed_design.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| No new dependencies | All changes use existing SQLAlchemy, Click, Jinja2 |

## Phase 1: Scorer & Dataset Seeds

**Goal:** `seed_scorers()` and `seed_datasets()` exist in `seed.py`, creating 7 scorers with versions and 3 datasets with versions and test cases.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1     | Completed | 2026-03-29 05:00 PM | 2026-03-29 05:05 PM | Add `SCORER_SEEDS` list and `seed_scorers(session)` to `ai_benchmark/eval/services/seed.py` — 7 built-in scorers with ScorerVersion default configs |
| 1.2     | Completed | 2026-03-29 05:00 PM | 2026-03-29 05:05 PM | Add `DATASET_SEEDS` list and `seed_datasets(session)` to `seed.py` — 3 datasets, 3 DatasetVersions, 30 TestCases |
| 1.3     | Completed | 2026-03-29 05:06 PM | 2026-03-29 05:07 PM | Run `ruff check` and `ruff format --check` on `seed.py` |
| 1.4     | Completed | 2026-03-29 05:07 PM | 2026-03-29 05:08 PM | Run `pytest tests/` — 879 passed |
| 1.5     | Completed | 2026-03-29 05:08 PM | 2026-03-29 05:09 PM | Stage all Phase 1 changes |
| 1.6     | Completed | 2026-03-29 05:09 PM | 2026-03-29 05:09 PM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Added `SCORER_SEEDS` (7 built-in scorers with default configs), `DATASET_SEEDS` (3 datasets, 30 test cases), `seed_scorers()`, `seed_datasets()` to seed.py. Updated `seed_all()` to include scorers and datasets. Updated test assertion. Created design doc and plan doc.
- **Changes hosted at:** `ai_benchmark/eval/services/seed.py`, `tests/test_eval/test_registry.py`, `docs/eval_seed_design.md`, `docs/eval_seed_plan.md`
- **Commit:** `Add scorer and dataset seed data to eval pipeline`

## Phase 2: Evaluation & Target Seeds

**Goal:** `seed_evaluations()` and `seed_targets()` exist in `seed.py`, creating 4 evaluation definitions with versions and 6 target configurations. `seed_all()` orchestrates all six seed functions in dependency order.
**Depends on:** Phase 1 (evaluation versions reference scorer and dataset version IDs).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1     | Completed | 2026-03-29 05:10 PM | 2026-03-29 05:14 PM | Add `EVALUATION_SEEDS` list and `seed_evaluations(session)` to `seed.py` — 4 definitions with EvaluationVersions referencing dataset_version and scorer_version IDs |
| 2.2     | Completed | 2026-03-29 05:10 PM | 2026-03-29 05:14 PM | Add `TARGET_SEEDS` list and `seed_targets(session)` to `seed.py` — 6 targets, 4 linked to runner/machine profiles |
| 2.3     | Completed | 2026-03-29 05:14 PM | 2026-03-29 05:14 PM | Update `seed_all()` to call all 6 seed functions in order: runners → machines → scorers → datasets → evaluations → targets |
| 2.4     | Completed | 2026-03-29 05:14 PM | 2026-03-29 05:15 PM | Run `ruff check` and `ruff format --check` on `seed.py` |
| 2.5     | Completed | 2026-03-29 05:15 PM | 2026-03-29 05:16 PM | Run `pytest tests/` — 879 passed |
| 2.6     | Completed | 2026-03-29 05:16 PM | 2026-03-29 05:16 PM | Stage all Phase 2 changes |
| 2.7     | Completed | 2026-03-29 05:16 PM | 2026-03-29 05:16 PM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Added `EVALUATION_SEEDS` (4 definitions), `TARGET_SEEDS` (6 configs), `seed_evaluations()`, `seed_targets()`, and helper resolvers. Updated `seed_all()` to orchestrate all 6 seed functions in dependency order. Updated test assertion.
- **Changes hosted at:** `ai_benchmark/eval/services/seed.py`, `tests/test_eval/test_registry.py`
- **Commit:** `Add evaluation and target seed data, wire seed_all orchestration`

## Phase 3: CLI Command & Launch Bug Fix

**Goal:** `ai-benchmark eval seed` CLI command works. The launch page reads the selected evaluation from the form instead of hardcoding `evaluation_version_id=1`.
**Depends on:** Phase 2 (seed functions must exist to expose via CLI).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Completed | 2026-03-29 05:17 PM | 2026-03-29 05:19 PM | Add `seed` Click command to `ai_benchmark/eval/cli/commands.py` that calls `seed_all(session)` and prints summary |
| 3.2     | Completed | 2026-03-29 05:19 PM | 2026-03-29 05:21 PM | Fix `run_launch_submit` in `ai_benchmark/eval/ui/server.py` — read `evaluation_id` from form, query latest EvaluationVersion, use its ID |
| 3.3     | Completed | 2026-03-29 05:21 PM | 2026-03-29 05:21 PM | Run `ruff check` and `ruff format --check` on modified files — clean |
| 3.4     | Completed | 2026-03-29 05:21 PM | 2026-03-29 05:22 PM | Run `pytest tests/` — 879 passed |
| 3.5     | Completed | 2026-03-29 05:22 PM | 2026-03-29 05:22 PM | Stage all Phase 3 changes |
| 3.6     | Completed | 2026-03-29 05:22 PM | 2026-03-29 05:22 PM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Added `eval seed` CLI command to `commands.py`. Fixed hardcoded `evaluation_version_id=1` in `run_launch_submit` to resolve the form-selected evaluation to its latest version.
- **Changes hosted at:** `ai_benchmark/eval/cli/commands.py`, `ai_benchmark/eval/ui/server.py`
- **Commit:** `Add eval seed CLI command, fix launch page evaluation selection`

## Phase 4: Seed & Verify

**Goal:** Run `ai-benchmark eval seed` against the database, verify the launch page shows evaluations and targets.
**Depends on:** Phase 3.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1     | Open   |               |                  | Run `ai-benchmark eval seed` — verify 7 scorers, 3 datasets, 4 evaluations, 6 targets created |
| 4.2     | Open   |               |                  | Run `ai-benchmark eval seed` a second time — verify idempotent (0 new records) |
| 4.3     | Open   |               |                  | Start eval server and verify `/eval/runs/launch` shows evaluations in dropdown and targets as checkboxes |
| 4.4     | Open   |               |                  | Run `pytest tests/` — full suite must pass |
| 4.5     | Open   |               |                  | Stage all Phase 4 changes (if any fixes needed) |
| 4.6     | Open   |               |                  | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Verify eval seed data and launch page functionality`
