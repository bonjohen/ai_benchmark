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
| 2.1     | Completed | 2026-03-29 05:44 PM | 2026-03-29 05:46 PM | Modify `SWEBenchCollector.extract_leaderboard()` in `swebench.py` — set `model=None` for multilingual variant, store subject in metadata |
| 2.2     | Completed | 2026-03-29 05:46 PM | 2026-03-29 05:47 PM | Update `BenchmarkCollector.extract_items()` in `__init__.py` — use `benchmark_subject` for title when model is None |
| 2.3     | Completed | 2026-03-29 05:47 PM | 2026-03-29 05:47 PM | Run `ruff check` and `ruff format --check` — clean |
| 2.4     | Completed | 2026-03-29 05:47 PM | 2026-03-29 05:48 PM | Run `pytest tests/` — 886 passed |
| 2.5     | Completed | 2026-03-29 05:48 PM | 2026-03-29 05:48 PM | Stage all Phase 2 changes |
| 2.6     | Completed | 2026-03-29 05:48 PM | 2026-03-29 05:48 PM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** SWE-bench multilingual variant now sets `model=None` on LeaderboardEntry, storing the language/repo name as `benchmark_subject` in metadata. BenchmarkCollector uses `benchmark_subject` for the title when model is None, and passes `model_hint=None`.
- **Changes hosted at:** `ai_benchmark/sources/benchmarks/swebench.py`, `ai_benchmark/sources/benchmarks/__init__.py`
- **Commit:** `Fix SWE-bench multilingual to not treat languages as models`

## Phase 3: Data Cleanup

**Goal:** Existing garbage model_slugs nulled out. Orphaned cross-references removed.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Completed | 2026-03-29 05:49 PM | 2026-03-29 05:52 PM | Write `cleanup_invalid_slugs(session)` in `normalizer.py` — nulls invalid model_slugs, removes orphaned xrefs |
| 3.2     | Completed | 2026-03-29 05:52 PM | 2026-03-29 05:53 PM | Add `cleanup-slugs` CLI command to `ai_benchmark/cli.py` |
| 3.3     | Completed | 2026-03-29 05:54 PM | 2026-03-29 05:54 PM | Run `ai-benchmark cleanup-slugs` — 61 events cleaned, 1311 xrefs removed |
| 3.4     | Completed | 2026-03-29 05:54 PM | 2026-03-29 05:55 PM | Verified `/eval/analysis/models` — no languages, repos, or aggregates. 588 valid model slugs remain, 0 invalid. |
| 3.5     | Completed | 2026-03-29 05:53 PM | 2026-03-29 05:54 PM | Run `pytest tests/` — 886 passed |
| 3.6     | Completed | 2026-03-29 05:55 PM | 2026-03-29 05:55 PM | Stage all Phase 3 changes |
| 3.7     | Completed | 2026-03-29 05:55 PM | 2026-03-29 05:55 PM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Added `cleanup_invalid_slugs()` async function to normalizer.py. Added `cleanup-slugs` CLI command. Ran cleanup: 61 events had model_slug nulled, 1311 orphaned cross-references removed. 588 valid model slugs remain.
- **Changes hosted at:** `ai_benchmark/processing/normalizer.py`, `ai_benchmark/cli.py`
- **Commit:** `Clean up invalid model slugs and orphaned cross-references`
