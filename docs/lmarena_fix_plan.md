# LMArena Collector Fix — Implementation Plan

**Source document:** `docs/lmarena_fix_design.md`

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
| No new dependencies | All changes use existing BeautifulSoup, regex, stdlib |

## Phase 1: Design + Plan Docs

**Goal:** Design doc and plan doc exist in `docs/`.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1     | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:10 PM | Write `docs/lmarena_fix_design.md` |
| 1.2     | Completed | 2026-03-29 06:10 PM | 2026-03-29 06:10 PM | Write `docs/lmarena_fix_plan.md` |
| 1.3     | Completed | 2026-03-29 06:11 PM | 2026-03-29 06:11 PM | Stage all Phase 1 changes |
| 1.4     | Completed | 2026-03-29 06:11 PM | 2026-03-29 06:11 PM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Created design doc analyzing root causes (wrong columns, model name mangling, missing Elo, hardcoded variant) and plan doc with 3 phases.
- **Changes hosted at:** `docs/lmarena_fix_design.md`, `docs/lmarena_fix_plan.md`
- **Commit:** `Add LMArena collector fix design and plan docs`

## Phase 2: Collector Fix + Tests

**Goal:** `LMArenaCollector.extract_leaderboard()` correctly parses model names, Elo scores, ranks, and variants from arena.ai HTML.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1     | Completed | 2026-03-29 06:15 PM | 2026-03-29 06:18 PM | Rewrite `extract_leaderboard()` in `ai_benchmark/sources/benchmarks/lmarena.py` — column detection, model name from `<a>` tag, Elo from score cell, rank from cells[0], variant from page URL |
| 2.2     | Completed | 2026-03-29 06:18 PM | 2026-03-29 06:20 PM | Add HTML fixture constants and tests in `tests/test_sources/test_collectors.py` — sub-page (7-col) and main page (4-col) layouts |
| 2.3     | Completed | 2026-03-29 06:20 PM | 2026-03-29 06:21 PM | Run `ruff check` and `ruff format --check` — clean |
| 2.4     | Completed | 2026-03-29 06:21 PM | 2026-03-29 06:22 PM | Run `pytest tests/` — 892 passed |
| 2.5     | Completed | 2026-03-29 06:22 PM | 2026-03-29 06:22 PM | Stage all Phase 2 changes |
| 2.6     | Completed | 2026-03-29 06:22 PM | 2026-03-29 06:22 PM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Rewrote `extract_leaderboard()` with helper functions `_extract_model_name()`, `_extract_org()`, `_extract_elo()`, `_variant_from_url()`. Detects 7-col vs 4-col layout. Extracts clean model name from `<a>` tag, Elo from score cell, org from secondary span, rank from cells[0]. Updated LMArena test to use realistic HTML fixture, changed base-class test to use LiveBenchCollector. Added 4 new LMArena tests.
- **Changes hosted at:** `ai_benchmark/sources/benchmarks/lmarena.py`, `tests/test_sources/test_collectors.py`, `tests/test_sources/test_benchmarks.py`
- **Commit:** `Fix LMArena collector to parse correct columns and extract clean model names`

## Phase 3: Data Cleanup + Config Update

**Goal:** All bad LMArena data removed. Source config updated to arena.ai domain.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Completed | 2026-03-29 06:23 PM | 2026-03-29 06:25 PM | Add `cleanup_lmarena_data(session)` to `ai_benchmark/processing/normalizer.py` — delete all LMArena events, claims, and xrefs |
| 3.2     | Completed | 2026-03-29 06:25 PM | 2026-03-29 06:26 PM | Add `cleanup-lmarena` CLI command to `ai_benchmark/cli.py` |
| 3.3     | Completed | 2026-03-29 06:26 PM | 2026-03-29 06:27 PM | Run `ai-benchmark cleanup-lmarena` — 441 events, 1343 claims, 43074 xrefs deleted |
| 3.4     | Completed | 2026-03-29 06:25 PM | 2026-03-29 06:25 PM | Update `ai_benchmark/config/sources.toml` — change `lmarena.ai` URLs to `arena.ai` |
| 3.5     | Completed | 2026-03-29 06:27 PM | 2026-03-29 06:28 PM | Run `pytest tests/` — 892 passed |
| 3.6     | Completed | 2026-03-29 06:28 PM | 2026-03-29 06:28 PM | Stage all Phase 3 changes |
| 3.7     | Completed | 2026-03-29 06:28 PM | 2026-03-29 06:28 PM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Added `cleanup_lmarena_data()` to normalizer.py (deletes all LMArena events + cascades to claims/xrefs). Added `cleanup-lmarena` CLI command. Updated sources.toml domain from `lmarena.ai` to `arena.ai`. Cleanup removed 441 events, 1343 claims, 43074 xrefs.
- **Changes hosted at:** `ai_benchmark/processing/normalizer.py`, `ai_benchmark/cli.py`, `ai_benchmark/config/sources.toml`
- **Commit:** `Clean up bad LMArena data and update source domain to arena.ai`
