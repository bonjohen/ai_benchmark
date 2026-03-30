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
| 2.1     | Open   |               |                  | Rewrite `extract_leaderboard()` in `ai_benchmark/sources/benchmarks/lmarena.py` — column detection, model name from `<a>` tag, Elo from score cell, rank from cells[0], variant from page URL |
| 2.2     | Open   |               |                  | Add HTML fixture constants and tests in `tests/test_sources/test_collectors.py` — sub-page (7-col) and main page (4-col) layouts |
| 2.3     | Open   |               |                  | Run `ruff check` and `ruff format --check` — clean |
| 2.4     | Open   |               |                  | Run `pytest tests/` — all pass |
| 2.5     | Open   |               |                  | Stage all Phase 2 changes |
| 2.6     | Open   |               |                  | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Fix LMArena collector to parse correct columns and extract clean model names`

## Phase 3: Data Cleanup + Config Update

**Goal:** All bad LMArena data removed. Source config updated to arena.ai domain.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Open   |               |                  | Add `cleanup_lmarena_data(session)` to `ai_benchmark/processing/normalizer.py` — delete all LMArena events, claims, and xrefs |
| 3.2     | Open   |               |                  | Add `cleanup-lmarena` CLI command to `ai_benchmark/cli.py` |
| 3.3     | Open   |               |                  | Run `ai-benchmark cleanup-lmarena` — verify all 441 events removed |
| 3.4     | Open   |               |                  | Update `ai_benchmark/config/sources.toml` — change `lmarena.ai` URLs to `arena.ai` |
| 3.5     | Open   |               |                  | Run `pytest tests/` — all pass |
| 3.6     | Open   |               |                  | Stage all Phase 3 changes |
| 3.7     | Open   |               |                  | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Clean up bad LMArena data and update source domain to arena.ai`
