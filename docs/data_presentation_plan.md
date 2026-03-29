# Data Presentation & Intelligence Products — Implementation Plan

**Source document:** `docs/data_presentation_pdr.md`

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
| Spearman correlation | Manual rank-based computation (stdlib `statistics` as fallback) |
| All other computation | stdlib `math`, `collections`, `statistics` |
| No new dependencies | N/A |

## Phase 1: Foundation — Types, Extended Fixtures

**Goal:** All new dataclasses exist in `types.py` and test fixtures provide multi-org, multi-benchmark data sufficient for all 7 products.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-29 02:30 PM | 2026-03-29 02:32 PM | Add 16 new dataclasses to `ai_benchmark/analysis/types.py`: SpotlightEntry, SpotlightReport, FrontierEntry, EvolutionSummary, BenchmarkPercentile, CapabilityProfile, OrgLandscapeEntry, LandscapeReport, CitationVelocityEntry, TopicTrend, ResearchPipelineReport, ModelVerification, BenchmarkVerification, VerificationReport, CorrelationEntry, CorrelationMatrix. Extend DigestReport with `spotlight_models` and `evolution_highlights` fields. |
| 1.2 | Completed | 2026-03-29 02:32 PM | 2026-03-29 02:35 PM | Extend `tests/test_analysis/conftest.py`: add second org (Anthropic) source+page, Claude-4-sonnet release event, benchmark events with extractable scores (GPT-5 SWE-bench 92.3%, GPT-5 MMLU 95.1%, Claude-4-sonnet SWE-bench 89.7%, Claude-4-sonnet MMLU 91.2%), cross-references (confirms link), claims at multiple confidence tiers (official_self_report, benchmark_owner_report, high_secondary). |
| 1.3 | Completed | 2026-03-29 02:35 PM | 2026-03-29 02:36 PM | Run `pytest` — all 133 analysis tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 1.4 | Open | | | Stage all Phase 1 changes. |
| 1.5 | Open | | | Commit: "Add presentation layer dataclasses and extended test fixtures". |

### Phase 1 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add presentation layer dataclasses and extended test fixtures`

## Phase 2: Tier 1 — Spotlight + Evolution Services

**Goal:** Products 1 and 2 (user's explicit requests) are fully functional with services, tests, CLI commands, API endpoints, and formatters.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Create `ai_benchmark/analysis/services/spotlight.py`: `get_spotlight()` composing `list_tracked_models`, `list_benchmarks`, `get_benchmark_leaderboard`, `get_recent_insights`, plus CrossReference count query. |
| 2.2 | Open | | | Create `ai_benchmark/analysis/services/evolution.py`: `get_benchmark_evolution()` composing `list_benchmarks`, `get_benchmark_timeline`, `get_benchmark_leaderboard` with rate-of-improvement, frontier progression, and saturation computation. |
| 2.3 | Open | | | Create `tests/test_analysis/test_spotlight.py`: 8 tests — empty DB, single model, multiple models, min_benchmarks filter, org filter, debut_strength ranking, xref count, insight flags. |
| 2.4 | Open | | | Create `tests/test_analysis/test_evolution.py`: 10 tests — empty DB, single benchmark, all benchmarks, rate computation, frontier progression, saturation percentage, saturation None for Elo, gap_to_second, window filtering, no scores. |
| 2.5 | Open | | | Add `spotlight_to_markdown()` and `evolution_to_markdown()` to `formatters/markdown.py`. Add `spotlight_to_csv()` and `evolution_to_csv()` to `formatters/csv_export.py`. |
| 2.6 | Open | | | Add `spotlight` and `evolution` CLI subcommands to `cli.py` following existing pattern. |
| 2.7 | Open | | | Add `/spotlight` and `/evolution` API endpoints to `api.py` following existing pattern. |
| 2.8 | Open | | | Add formatter tests for spotlight and evolution to `test_formatters.py`. |
| 2.9 | Open | | | Run `pytest` — all tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 2.10 | Open | | | Stage all Phase 2 changes. |
| 2.11 | Open | | | Commit: "Add spotlight and evolution intelligence products (Tier 1)". |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add spotlight and evolution intelligence products (Tier 1)`

## Phase 3: Tier 2a — Capability + Landscape Services

**Goal:** Products 3 and 4 (cross-benchmark capability profiles and competitive landscape) are fully functional.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-29 03:40 PM | 2026-03-29 03:45 PM | Create `ai_benchmark/analysis/services/capability.py`: `get_capability_profile()` and `compare_capabilities()` with direct score extraction via `extract_benchmark_score()`, percentile normalization, and composite scoring. |
| 3.2 | Completed | 2026-03-29 03:45 PM | 2026-03-29 03:50 PM | Create `ai_benchmark/analysis/services/landscape.py`: `get_landscape()` composing `get_activity_timeline`, `list_tracked_models`, `extract_benchmark_score` with per-org benchmark aggregation and trend computation. |
| 3.3 | Completed | 2026-03-29 03:50 PM | 2026-03-29 03:55 PM | Create `tests/test_analysis/test_capability.py`: 8 tests — empty DB, single model, percentile computation, composite score, compare multi-model, model not found, no benchmark data, top scorer percentile. |
| 3.4 | Completed | 2026-03-29 03:55 PM | 2026-03-29 04:00 PM | Create `tests/test_analysis/test_landscape.py`: 7 tests — empty DB, single org, multi-org, new model detection, pricing events, benchmark breadth, trend computation. |
| 3.5 | Completed | 2026-03-29 04:00 PM | 2026-03-29 04:05 PM | Add `capability_to_markdown()` and `landscape_to_markdown()` to `formatters/markdown.py`. |
| 3.6 | Completed | 2026-03-29 04:05 PM | 2026-03-29 04:10 PM | Add `capability` and `landscape` CLI subcommands to `cli.py`. Add formatter tests for capability and landscape to `test_formatters.py`. |
| 3.7 | Completed | 2026-03-29 04:10 PM | 2026-03-29 04:15 PM | Add `/capability/{slug}`, `/capability`, and `/landscape` API endpoints to `api.py`. |
| 3.8 | Completed | 2026-03-29 04:15 PM | 2026-03-29 04:30 PM | Run `pytest` — 842 passed. Run `ruff check` and `ruff format --check` — clean. |
| 3.9 | Completed | 2026-03-29 04:30 PM | 2026-03-29 04:32 PM | Stage all Phase 3 changes. |
| 3.10 | Completed | 2026-03-29 04:32 PM | 2026-03-29 04:33 PM | Commit: "Add capability profiles and competitive landscape (Tier 2a)". |

### Phase 3 Summary

- **Changes:** Created `capability.py` (percentile normalization, composite scoring via direct score extraction) and `landscape.py` (org-level benchmark aggregation, pricing context, trend computation). Added `capability_to_markdown()` and `landscape_to_markdown()` formatters. Added `capability` and `landscape` CLI subcommands and 3 API endpoints. 8 capability tests + 7 landscape tests + 4 formatter tests = 19 new tests. Total: 842 passed.
- **Changes hosted at:** TBD
- **Commit:** `Add capability profiles and competitive landscape (Tier 2a)`

## Phase 4: Tier 2b — Research Pipeline Service

**Goal:** Product 5 (research-to-product pipeline intelligence) is fully functional.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-29 04:35 PM | 2026-03-29 04:42 PM | Create `ai_benchmark/analysis/services/research_pipeline.py`: `get_research_pipeline()` composing `get_citation_leaders`, `detect_paper_to_product` with citation velocity, split-window topic trends, and predictive signals. |
| 4.2 | Completed | 2026-03-29 04:42 PM | 2026-03-29 04:45 PM | Create `tests/test_analysis/test_research_pipeline.py`: 7 tests — empty DB, velocity computation, velocity values, topic trends, topic direction, min_citations filter, paper-product links. |
| 4.3 | Completed | 2026-03-29 04:45 PM | 2026-03-29 04:48 PM | Add `research_pipeline_to_markdown()` to `formatters/markdown.py`. Add 3 formatter tests to `test_formatters.py`. |
| 4.4 | Completed | 2026-03-29 04:48 PM | 2026-03-29 04:52 PM | Add `research-pipeline` CLI subcommand to `cli.py`. Add `/research-pipeline` API endpoint to `api.py`. |
| 4.5 | Completed | 2026-03-29 04:52 PM | 2026-03-29 04:55 PM | Run `pytest` — 852 passed. Run `ruff check` and `ruff format --check` — clean. |
| 4.6 | Completed | 2026-03-29 04:55 PM | 2026-03-29 04:56 PM | Stage all Phase 4 changes. |
| 4.7 | Completed | 2026-03-29 04:56 PM | 2026-03-29 04:57 PM | Commit: "Add research-to-product pipeline intelligence (Tier 2b)". |

### Phase 4 Summary

- **Changes:** Created `research_pipeline.py` (citation velocity, split-window topic trends, predictive signals). Added `research_pipeline_to_markdown()` formatter. Added `research-pipeline` CLI subcommand and `/research-pipeline` API endpoint. 7 service tests + 3 formatter tests = 10 new tests. Total: 852 passed.
- **Changes hosted at:** TBD
- **Commit:** `Add research-to-product pipeline intelligence (Tier 2b)`

## Phase 5: Tier 3 — Verification + Correlation Services

**Goal:** Products 6 and 7 (claim verification and benchmark correlation) are fully functional.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-03-29 05:00 PM | 2026-03-29 05:08 PM | Create `ai_benchmark/analysis/services/verification.py`: `get_verification_report()` querying EventRecord, ClaimRecord, CrossReference for confirmation depth, confidence tier distribution, and score variance. |
| 5.2 | Completed | 2026-03-29 05:08 PM | 2026-03-29 05:15 PM | Create `ai_benchmark/analysis/services/correlation.py`: `get_correlation_matrix()` with `extract_benchmark_score()`, Spearman rank correlation, label assignment, and cluster detection. |
| 5.3 | Completed | 2026-03-29 05:15 PM | 2026-03-29 05:20 PM | Create `tests/test_analysis/test_verification.py`: 11 tests — empty DB, model counts, confirmed pct, conflicted pct, model detail, source count, tier distribution, xref count, benchmark detail, org filter, model filter. |
| 5.4 | Completed | 2026-03-29 05:20 PM | 2026-03-29 05:25 PM | Create `tests/test_analysis/test_correlation.py`: 8 tests — empty DB, with data, entries validation, high min_overlap, perfect positive/negative correlation, rank ties, label assignment. |
| 5.5 | Completed | 2026-03-29 05:25 PM | 2026-03-29 05:30 PM | Add `verification_to_markdown()`, `correlation_to_markdown()` to `formatters/markdown.py`. Add `verification_to_csv()`, `correlation_to_csv()` to `formatters/csv_export.py`. |
| 5.6 | Completed | 2026-03-29 05:30 PM | 2026-03-29 05:35 PM | Add `verification` and `correlations` CLI subcommands to `cli.py`. Add 6 formatter tests to `test_formatters.py`. |
| 5.7 | Completed | 2026-03-29 05:35 PM | 2026-03-29 05:38 PM | Add `/verification` and `/correlations` API endpoints to `api.py`. |
| 5.8 | Completed | 2026-03-29 05:38 PM | 2026-03-29 05:42 PM | Run `pytest` — 877 passed. Run `ruff check` and `ruff format --check` — clean. |
| 5.9 | Completed | 2026-03-29 05:42 PM | 2026-03-29 05:43 PM | Stage all Phase 5 changes. |
| 5.10 | Completed | 2026-03-29 05:43 PM | 2026-03-29 05:44 PM | Commit: "Add claim verification and benchmark correlation (Tier 3)". |

### Phase 5 Summary

- **Changes:** Created `verification.py` (per-model/per-benchmark claim analysis, confidence tier distribution, CrossReference confirms count, score variance) and `correlation.py` (Spearman rank correlation, label assignment, clique-based cluster detection). Added formatters (markdown + CSV) for both. Added `verification` and `correlations` CLI subcommands and 2 API endpoints. 11 verification tests + 8 correlation tests + 6 formatter tests = 25 new tests. Total: 877 passed.
- **Changes hosted at:** TBD
- **Commit:** `Add claim verification and benchmark correlation (Tier 3)`

## Phase 6: Digest Integration + Documentation

**Goal:** Weekly digest includes spotlight and evolution highlights. CLAUDE.md updated with new commands and architecture. All tests pass.
**Depends on:** Phases 2, 3, 4, 5.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-03-29 05:48 PM | 2026-03-29 05:50 PM | Modify `ai_benchmark/analysis/services/digest.py`: import and call `get_spotlight` and `get_benchmark_evolution`, populate `spotlight_models` and `evolution_highlights` on DigestReport. |
| 6.2 | Completed | 2026-03-29 05:48 PM | 2026-03-29 05:50 PM | `digest_to_markdown()` already renders spotlight and evolution sections (added in Phase 2). No changes needed. |
| 6.3 | Completed | 2026-03-29 05:50 PM | 2026-03-29 05:53 PM | Update `tests/test_analysis/test_digest.py`: added `test_generate_digest_spotlight` and `test_generate_digest_evolution`. |
| 6.4 | Completed | 2026-03-29 05:53 PM | 2026-03-29 05:58 PM | Update `CLAUDE.md`: added 7 new CLI commands, updated Analysis Architecture with 12 services, 31 dataclasses, 14 formatters, 7 CSV exporters, 16 CLI subcommands, 18 API endpoints, test count 879. |
| 6.5 | Completed | 2026-03-29 05:58 PM | 2026-03-29 06:02 PM | Run `pytest` — 879 passed. Run `ruff check` and `ruff format --check` — clean. |
| 6.6 | Started | 2026-03-29 06:02 PM | | Stage all Phase 6 changes. |
| 6.7 | Open | | | Commit: "Integrate spotlight and evolution into digest, update documentation". |

### Phase 6 Summary

- **Changes:** Modified `digest.py` to call `get_spotlight` and `get_benchmark_evolution`, populating `spotlight_models` and `evolution_highlights` on DigestReport. Updated CLAUDE.md with complete analysis architecture (12 services, 31 dataclasses, 14 markdown renderers, 7 CSV exporters, 16 CLI subcommands, 18 API endpoints). Added 2 digest tests. Total: 879 passed.
- **Changes hosted at:** TBD
- **Commit:** `Integrate spotlight and evolution into digest, update documentation`
