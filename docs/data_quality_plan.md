# Data Quality: Model Slug Validation — Implementation Plan

**Source document:** `docs/data_quality_design.md`

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
| No new dependencies | All changes use existing SQLAlchemy, regex, stdlib |

## Phase 1: Slug Validation in Normalizer

**Goal:** `validate_model_slug()` exists in `normalizer.py` with blocklist. Pipeline uses it to gate all model slugs.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1     | Completed | 2026-03-29 05:35 PM | 2026-03-29 05:38 PM | Add `_NON_MODEL_BLOCKLIST` set and `validate_model_slug(slug) -> str | None` to `ai_benchmark/processing/normalizer.py` |
| 1.2     | Completed | 2026-03-29 05:38 PM | 2026-03-29 05:39 PM | Modify `process_item()` in `ai_benchmark/processing/pipeline.py` line 71 to validate model_hint through `validate_model_slug()` |
| 1.3     | Completed | 2026-03-29 05:39 PM | 2026-03-29 05:41 PM | Add 7 unit tests for `validate_model_slug()` in `tests/test_sources/test_collectors.py` — real models pass, blocklist items rejected |
| 1.4     | Completed | 2026-03-29 05:41 PM | 2026-03-29 05:41 PM | Run `ruff check` and `ruff format --check` — clean |
| 1.5     | Completed | 2026-03-29 05:41 PM | 2026-03-29 05:42 PM | Run `pytest tests/` — 886 passed |
| 1.6     | Completed | 2026-03-29 05:42 PM | 2026-03-29 05:42 PM | Stage all Phase 1 changes |
| 1.7     | Completed | 2026-03-29 05:42 PM | 2026-03-29 05:42 PM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Added `_NON_MODEL_BLOCKLIST` (50+ entries covering languages, aggregates, years, feature terms) and `validate_model_slug()` to normalizer.py. Wired validation into pipeline.py at the model_hint gate. Added 7 test functions covering all rejection categories.
- **Changes hosted at:** `ai_benchmark/processing/normalizer.py`, `ai_benchmark/processing/pipeline.py`, `tests/test_sources/test_collectors.py`
- **Commit:** `Add model slug validation to normalizer and pipeline`

## Phase 2: SWE-bench Multilingual Fix

**Goal:** SWE-bench multilingual variant produces `model_hint=None` instead of language/repo names.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1     | Open   |               |                  | Modify `SWEBenchCollector.extract_leaderboard()` in `ai_benchmark/sources/benchmarks/swebench.py` to set `model=None` for multilingual variant, store subject in metadata |
| 2.2     | Open   |               |                  | Update `BenchmarkCollector.extract_items()` in `ai_benchmark/sources/benchmarks/__init__.py` to handle `entry.model=None` gracefully |
| 2.3     | Open   |               |                  | Run `ruff check` and `ruff format --check` on modified files |
| 2.4     | Open   |               |                  | Run `pytest tests/` — full suite must pass |
| 2.5     | Open   |               |                  | Stage all Phase 2 changes |
| 2.6     | Open   |               |                  | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Fix SWE-bench multilingual to not treat languages as models`

## Phase 3: Data Cleanup

**Goal:** Existing garbage model_slugs nulled out. Orphaned cross-references removed.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Open   |               |                  | Write cleanup function in `ai_benchmark/processing/normalizer.py` — `async def cleanup_invalid_slugs(session)` that nulls invalid model_slugs and removes orphaned xrefs |
| 3.2     | Open   |               |                  | Add `cleanup-slugs` CLI command to `ai_benchmark/cli.py` that runs the cleanup |
| 3.3     | Open   |               |                  | Run `ai-benchmark cleanup-slugs` — report counts of cleaned records |
| 3.4     | Open   |               |                  | Verify `/eval/analysis/models` no longer shows programming languages or repos |
| 3.5     | Open   |               |                  | Run `pytest tests/` — full suite must pass |
| 3.6     | Open   |               |                  | Stage all Phase 3 changes |
| 3.7     | Open   |               |                  | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Clean up invalid model slugs and orphaned cross-references`
