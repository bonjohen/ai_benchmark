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
| 1.1 | Open | | | Add `_CAMEL_BOUNDARY` regex and `_repair_whitespace()` function to `processing/normalizer.py`. Inserts spaces at lowercase→uppercase boundaries (fixes "launchedClaude" → "launched Claude"). |
| 1.2 | Open | | | Add `_KNOWN_MODEL_NAMES` dictionary to `processing/normalizer.py` — ~40 entries mapping display names to canonical slugs (Claude variants, GPT variants, Gemini, Grok, Mistral, Command, Llama). |
| 1.3 | Open | | | Add `_match_known_model()` helper to `processing/normalizer.py` — normalizes input text (lowercase, collapse whitespace), applies `_repair_whitespace()`, searches for longest dictionary key match as substring, returns canonical slug or None. |
| 1.4 | Open | | | Modify `extract_model_slug()` in `processing/normalizer.py` — call `_repair_whitespace()` on input text, try `_match_known_model()` first, fall back to existing regex patterns only if dictionary returns None. |
| 1.5 | Open | | | Add `backfill-slugs` command to `analysis/cli.py` — query events where `model_slug IS NULL`, run improved `extract_model_slug()` against `title + " " + (raw_content or "")`, update records where slug found, report count. |
| 1.6 | Open | | | Create `tests/test_slug_extraction.py` — test whitespace repair ("launchedClaude" → "launched Claude"), dictionary matching ("We've launched Claude Opus 4.6" → "claude-opus-4.6"), regex fallback for unknown models, no false positives on non-model text. |
| 1.7 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 1.8 | Open | | | Stage all Phase 1 changes. |
| 1.9 | Open | | | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Enhance model slug extraction with dictionary lookup and whitespace repair`

---

## Phase 2: LMArena Event Type and Elo Score Fix

**Goal:** LMArena benchmark entries are correctly typed as `benchmark_result`. Elo scores appear in `raw_content` for both new and existing events. A backfill command fixes existing records.
**Depends on:** Nothing (independent of Phase 1).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Add benchmark_variant override in `processing/pipeline.py:process_item()` — after `event_type = classify_event_type(...)`, if `item.metadata.get("benchmark_variant")` is truthy and event_type is `"announcement"`, override to `"benchmark_result"`. |
| 2.2 | Open | | | Modify `sources/benchmarks/__init__.py:BenchmarkCollector.extract_items()` — change `body` template from `f"Rank: {entry.rank}, Variant: {variant}, Conditions: {conditions}"` to include score: `f"Rank: {entry.rank}, Score: {entry.score}, Variant: {variant}, Conditions: {conditions}"` (skip Score field if entry.score is None). |
| 2.3 | Open | | | Add `backfill-types` command to `analysis/cli.py` — (a) UPDATE event_type to `benchmark_result` where `benchmark_variant IS NOT NULL AND event_type = 'announcement'`, (b) for LMArena events with `raw_content LIKE 'Rank:%' AND raw_content NOT LIKE '%Score:%'`, find associated claim with `claim_text LIKE 'LMArena:%=%'`, extract numeric Elo value via regex `= (\d+)`, update raw_content to insert `Score: {elo}` after `Rank: N`. Report counts for both operations. |
| 2.4 | Open | | | Create `tests/test_lmarena_fixes.py` — test event type override (item with benchmark_variant metadata gets `benchmark_result` not `announcement`), test body template includes Score, test backfill regex extracts Elo from claim_text. |
| 2.5 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 2.6 | Open | | | Stage all Phase 2 changes. |
| 2.7 | Open | | | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Fix LMArena event typing and add Elo scores to raw_content`

---

## Phase 3: Cross-Reference Tightening

**Goal:** The supplements strategy no longer creates a combinatorial explosion. Cross-reference count drops from 333K to a meaningful number.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Modify `processing/cross_reference.py:build_cross_references()` — skip strategy 2 (org + event_type) if `event.model_slug is None`. |
| 3.2 | Open | | | Modify `processing/cross_reference.py:find_related_by_org_event_type()` — add `.where(EventRecord.model_slug.is_not(None))` to the query so it only matches events that also have a slug. |
| 3.3 | Open | | | Add supplement cap in `build_cross_references()` — after each strategy's `find_related_*` call, slice result to `[:10]` before creating CrossReference records. |
| 3.4 | Open | | | Create `tests/test_crossref_tightening.py` — test that events without model_slug produce 0 supplements, test cap limits results to 10, test that confirms and cites strategies are unaffected. |
| 3.5 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 3.6 | Open | | | Stage all Phase 3 changes. |
| 3.7 | Open | | | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Tighten cross-reference supplements to require model_slug and cap at 10`

---

## Phase 4: Source and Page Table Population

**Goal:** The `sources` and `pages` tables are populated on first collection. The `ai-benchmark status` command shows non-zero event counts per source.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Modify `coordination/coordinator.py:_create_tasks()` — when `source_record is None`, create a new `Source` ORM record from `source_config` fields (source_name, category, organization, homepage_url, base_domain, trust_rating, source_role, classification, collection_method), add to session, flush to get ID. |
| 4.2 | Open | | | Verify existing page creation logic (already at line 168-174) works when source_id is now always valid (>0). No change expected — just confirm. |
| 4.3 | Open | | | Create `tests/test_source_population.py` — test that after coordinator processes a source config, a Source record exists in DB with matching organization. Test that Page records are created for each page config. |
| 4.4 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 4.5 | Open | | | Stage all Phase 4 changes. |
| 4.6 | Open | | | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Populate sources and pages tables from catalog on first collection`

---

## Phase 5: Research Enrichment Retry

**Goal:** Pending candidate papers are retried on subsequent collection runs. With an API key configured, papers progress from `pending` to `enriched`.
**Depends on:** Nothing (independent).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Modify `sources/research/semantic_scholar.py:collect_via_api()` — after processing fresh queries, add a retry loop: query `CandidatePaper` where `status = 'pending'` and `retry_count < 3`, limit 10, ordered by `discovered_at`. For each, attempt enrichment via `self.client.get_paper_by_arxiv()` or `self.client.search_paper()`, increment `retry_count` and set `last_retry_at`. Wrap in try/except to continue on individual failures. |
| 5.2 | Open | | | Add `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY=` to `scripts/env.dev.template` with a comment explaining it's recommended for research enrichment. |
| 5.3 | Open | | | Create `tests/test_research_retry.py` — test that pending candidates with retry_count < 3 are selected, test that retry_count increments, test that candidates with retry_count >= 3 are skipped. |
| 5.4 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 5.5 | Open | | | Stage all Phase 5 changes. |
| 5.6 | Open | | | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add research enrichment retry for pending candidate papers`

---

## Phase 6: Deploy, Backfill, and Re-seed

**Goal:** All fixes are deployed to production. Backfill commands correct existing data. Model registry is re-seeded with improved data.
**Depends on:** Phases 1-5.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Build wheel: `python -m build --wheel --outdir dist/` |
| 6.2 | Open | | | Install to production: `C:\ai-benchmark\venv\Scripts\pip install --force-reinstall --no-deps dist\ai_benchmark-0.1.0-py3-none-any.whl` |
| 6.3 | Open | | | Run `ai-benchmark analyze backfill-slugs` — verify >60% of 2,402 NULL-slug events updated. Record count. |
| 6.4 | Open | | | Run `ai-benchmark analyze backfill-types` — verify 0 events with `event_type='announcement' AND benchmark_variant IS NOT NULL`. Verify Elo scores in raw_content. |
| 6.5 | Open | | | Purge stale cross-references: `DELETE FROM cross_references WHERE relationship_type='supplements'` via a one-time script. |
| 6.6 | Open | | | Run `ai-benchmark analyze seed-models` — verify entity count decreases (better dedup from improved slugs). |
| 6.7 | Open | | | Restart server: `ai-benchmark eval serve`. Verify `/eval/analysis` shows updated model count, benchmarks show Elo scores, verification claims are correct. |
| 6.8 | Open | | | Run a test collection: `ai-benchmark collect --source Anthropic` — verify sources/pages tables populated, events have model_slugs, cross-ref count is reasonable. |
| 6.9 | Open | | | Stage all Phase 6 changes (plan doc updates only). |
| 6.10 | Open | | | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Deploy pipeline fixes, run backfills, re-seed model registry`
