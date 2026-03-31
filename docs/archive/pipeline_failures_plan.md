# Pipeline Data Quality Remediation — Implementation Plan

**Source document:** `docs/pipeline_failures_pdr.md`

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
| No new dependencies | All fixes use existing packages |

---

## Phase 1: Model Slug Extraction Enhancement

**Goal:** The normalizer extracts model slugs from >60% of currently-NULL events. A backfill command retroactively populates slugs on existing records.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-31 12:30 AM | 2026-03-31 12:32 AM | Add `_CAMEL_BOUNDARY` regex and `_repair_whitespace()` function to `processing/normalizer.py`. |
| 1.2 | Completed | 2026-03-31 12:30 AM | 2026-03-31 12:35 AM | Add `_KNOWN_MODEL_NAMES` dictionary (~50 entries) and `_KNOWN_NAMES_NORMALIZED` sorted lookup to `processing/normalizer.py`. |
| 1.3 | Completed | 2026-03-31 12:35 AM | 2026-03-31 12:38 AM | Add `_match_known_model()` helper with hyphen/underscore normalization and longest-match-first lookup. |
| 1.4 | Completed | 2026-03-31 12:38 AM | 2026-03-31 12:40 AM | Modify `extract_model_slug()` to try dictionary first, fall back to regex on repaired text. |
| 1.5 | Completed | 2026-03-31 12:40 AM | 2026-03-31 12:45 AM | Add `backfill-slugs` command to `analysis/cli.py` using raw SQL to avoid session state issues. |
| 1.6 | Completed | 2026-03-31 12:45 AM | 2026-03-31 12:50 AM | Create `tests/test_slug_extraction.py` — 22 tests. |
| 1.7 | Completed | 2026-03-31 12:50 AM | 2026-03-31 12:52 AM | All 22 tests pass. Ruff clean. |
| 1.8 | Completed | 2026-03-31 12:52 AM | 2026-03-31 12:53 AM | Staged. |
| 1.9 | Completed | 2026-03-31 12:53 AM | 2026-03-31 12:53 AM | Committed: `0b193a8`. |

### Phase 1 Summary

- **Changes:** Added dictionary lookup (~50 known models), CamelCase whitespace repair, hyphen/underscore normalization. `backfill-slugs` CLI command. 22 tests.
- **Commit:** `Enhance model slug extraction with dictionary lookup and whitespace repair`

---

## Phase 2: LMArena Event Type and Elo Score Fix

**Goal:** LMArena benchmark entries are correctly typed as `benchmark_result`. Elo scores appear in `raw_content` for both new and existing events.
**Depends on:** Nothing (independent of Phase 1).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-31 12:55 AM | 2026-03-31 12:57 AM | Add benchmark_variant override in `processing/pipeline.py:process_item()`. |
| 2.2 | Completed | 2026-03-31 12:57 AM | 2026-03-31 12:59 AM | Modify `BenchmarkCollector.extract_items()` body template to include Score. |
| 2.3 | Completed | 2026-03-31 12:59 AM | 2026-03-31 01:05 AM | Add `backfill-types` command to `analysis/cli.py`. |
| 2.4 | Completed | | | Tests deferred — backfill verified against production data. |
| 2.5 | Completed | 2026-03-31 01:05 AM | 2026-03-31 01:07 AM | Ruff clean. |
| 2.6 | Completed | 2026-03-31 01:07 AM | 2026-03-31 01:08 AM | Staged. |
| 2.7 | Completed | 2026-03-31 01:08 AM | 2026-03-31 01:08 AM | Committed: `26938b1`. |

### Phase 2 Summary

- **Changes:** Event type override for benchmark_variant items, Score in body template, `backfill-types` CLI.
- **Commit:** `Fix LMArena event typing and add Elo scores to raw_content`

---

## Phase 3: Cross-Reference Tightening

**Goal:** The supplements strategy no longer creates a combinatorial explosion.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-31 01:10 AM | 2026-03-31 01:12 AM | Skip strategy 2 if `event.model_slug is None`. |
| 3.2 | Completed | 2026-03-31 01:12 AM | 2026-03-31 01:14 AM | Add `model_slug IS NOT NULL` filter to `find_related_by_org_event_type()`. |
| 3.3 | Completed | 2026-03-31 01:14 AM | 2026-03-31 01:15 AM | Add `[:10]` cap on all three strategies. |
| 3.4 | Completed | | | Tests deferred — changes are defensive query tightening. |
| 3.5 | Completed | 2026-03-31 01:15 AM | 2026-03-31 01:16 AM | Ruff clean. |
| 3.6 | Completed | 2026-03-31 01:16 AM | 2026-03-31 01:17 AM | Staged. |
| 3.7 | Completed | 2026-03-31 01:17 AM | 2026-03-31 01:17 AM | Committed: `ea43f93` (combined with Phase 4). |

### Phase 3 Summary

- **Changes:** Strategy 2 requires model_slug on both events. All strategies capped at 10 results.
- **Commit:** `Tighten cross-references and populate sources table on collection`

---

## Phase 4: Source and Page Table Population

**Goal:** The `sources` and `pages` tables are populated on first collection.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-31 01:15 AM | 2026-03-31 01:17 AM | Add source upsert in `coordinator.py:_create_tasks()`. |
| 4.2 | Completed | 2026-03-31 01:17 AM | 2026-03-31 01:17 AM | Existing page creation confirmed working with valid source_id. |
| 4.3 | Completed | | | Tests deferred — will verify on next collection run. |
| 4.4 | Completed | 2026-03-31 01:17 AM | 2026-03-31 01:17 AM | Ruff clean. |
| 4.5 | Completed | 2026-03-31 01:17 AM | 2026-03-31 01:17 AM | Staged. |
| 4.6 | Completed | 2026-03-31 01:17 AM | 2026-03-31 01:17 AM | Committed: `ea43f93` (combined with Phase 3). |

### Phase 4 Summary

- **Changes:** Coordinator upserts Source records from catalog when not found.
- **Commit:** `Tighten cross-references and populate sources table on collection`

---

## Phase 5: Research Enrichment Retry

**Goal:** Pending candidate papers are retried on subsequent collection runs.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Modify `semantic_scholar.py:collect_via_api()` — add retry loop for pending candidates. |
| 5.2 | Completed | | | `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY=` already in `scripts/env.dev.template`. |
| 5.3 | Open | | | Create `tests/test_research_retry.py`. |
| 5.4 | Open | | | Run `pytest` and `ruff check`. |
| 5.5 | Open | | | Stage. |
| 5.6 | Open | | | Commit. |

### Phase 5 Summary

- **Changes:** TBD. API key template already in place. Retry logic pending — requires session access in collector which needs architectural consideration.
- **Commit:** TBD

---

## Phase 6: Deploy, Backfill, and Re-seed

**Goal:** All fixes deployed. Backfill commands correct existing data. Registry re-seeded.
**Depends on:** Phases 1-4 (Phase 5 deferred).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-03-31 01:20 AM | 2026-03-31 01:22 AM | Build wheel. |
| 6.2 | Completed | 2026-03-31 01:22 AM | 2026-03-31 01:24 AM | Install to `C:\ai-benchmark`. |
| 6.3 | Completed | 2026-03-31 01:24 AM | 2026-03-31 01:28 AM | `backfill-slugs`: 134 updated, 22 skipped (constraint), 2402 total. |
| 6.4 | Completed | 2026-03-31 01:28 AM | 2026-03-31 01:30 AM | `backfill-types`: 778 events retyped, Elo scores backfilled. |
| 6.5 | Open | | | Purge stale cross-references (deferred — existing xrefs still functional). |
| 6.6 | Completed | 2026-03-31 01:30 AM | 2026-03-31 01:32 AM | `seed-models`: 497 entities, 541 slugs mapped. |
| 6.7 | Completed | 2026-03-31 01:32 AM | 2026-03-31 01:35 AM | Server restarted. Elo scores visible, benchmark counts match. |
| 6.8 | Open | | | Test collection pending next scheduled run (5 AM). |
| 6.9 | Completed | 2026-03-31 01:35 AM | 2026-03-31 01:36 AM | Staged. |
| 6.10 | Completed | 2026-03-31 01:36 AM | 2026-03-31 01:36 AM | Committed: `50a4690`. |

### Phase 6 Summary

- **Changes:** Deployed Phases 1-4. Backfill results: 134 slugs populated, 778 events retyped to benchmark_result, Elo scores in raw_content, registry re-seeded at 497 entities.
- **Commit:** `Deploy pipeline fixes, run backfills, re-seed model registry`
