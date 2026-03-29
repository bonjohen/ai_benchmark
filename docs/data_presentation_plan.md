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
| 3.1 | Open | | | Create `ai_benchmark/analysis/services/capability.py`: `get_capability_profile()` and `compare_capabilities()` composing `build_model_profile`, `get_benchmark_leaderboard` with percentile normalization and composite scoring. |
| 3.2 | Open | | | Create `ai_benchmark/analysis/services/landscape.py`: `get_landscape()` composing `get_activity_timeline`, `list_tracked_models`, `get_recent_insights` with per-org benchmark aggregation and trend computation. |
| 3.3 | Open | | | Create `tests/test_analysis/test_capability.py`: 8 tests — empty DB, single model, percentile computation, composite score, compare multi-model, model not found, single benchmark, equal-score tie. |
| 3.4 | Open | | | Create `tests/test_analysis/test_landscape.py`: 7 tests — empty DB, single org, multi-org ranking, new model detection, pricing events, cluster count, trend computation. |
| 3.5 | Open | | | Add `capability_to_markdown()` and `landscape_to_markdown()` to `formatters/markdown.py`. |
| 3.6 | Open | | | Add `capability` and `landscape` CLI subcommands to `cli.py`. Add formatter tests for capability and landscape to `test_formatters.py`. |
| 3.7 | Open | | | Add `/capability/{slug}`, `/capability`, and `/landscape` API endpoints to `api.py`. |
| 3.8 | Open | | | Run `pytest` — all tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 3.9 | Open | | | Stage all Phase 3 changes. |
| 3.10 | Open | | | Commit: "Add capability profiles and competitive landscape (Tier 2a)". |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add capability profiles and competitive landscape (Tier 2a)`

## Phase 4: Tier 2b — Research Pipeline Service

**Goal:** Product 5 (research-to-product pipeline intelligence) is fully functional.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Create `ai_benchmark/analysis/services/research_pipeline.py`: `get_research_pipeline()` composing `get_citation_leaders`, `detect_paper_to_product` with citation velocity, split-window topic trends, and predictive signals. |
| 4.2 | Open | | | Create `tests/test_analysis/test_research_pipeline.py`: 7 tests — empty DB, velocity computation, topic trends rising/falling/stable, predictive signals, no papers, min_citations filter, paper-product enrichment. |
| 4.3 | Open | | | Add `research_pipeline_to_markdown()` to `formatters/markdown.py`. Add formatter test to `test_formatters.py`. |
| 4.4 | Open | | | Add `research-pipeline` CLI subcommand to `cli.py`. Add `/research-pipeline` API endpoint to `api.py`. |
| 4.5 | Open | | | Run `pytest` — all tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 4.6 | Open | | | Stage all Phase 4 changes. |
| 4.7 | Open | | | Commit: "Add research-to-product pipeline intelligence (Tier 2b)". |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add research-to-product pipeline intelligence (Tier 2b)`

## Phase 5: Tier 3 — Verification + Correlation Services

**Goal:** Products 6 and 7 (claim verification and benchmark correlation) are fully functional.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Create `ai_benchmark/analysis/services/verification.py`: `get_verification_report()` querying EventRecord, ClaimRecord, CrossReference for confirmation depth, confidence tier distribution, and score variance. |
| 5.2 | Open | | | Create `ai_benchmark/analysis/services/correlation.py`: `get_correlation_matrix()` with `extract_benchmark_score()`, Spearman rank correlation, label assignment, and cluster detection. |
| 5.3 | Open | | | Create `tests/test_analysis/test_verification.py`: 8 tests — empty DB, model verification, confirmed pct, conflicted pct, source count, confidence tier ordering, benchmark variance, system summary. |
| 5.4 | Open | | | Create `tests/test_analysis/test_correlation.py`: 7 tests — empty DB, sufficient overlap, insufficient overlap, correlation computation, label assignment, cluster detection, single benchmark. |
| 5.5 | Open | | | Add `verification_to_markdown()` and `correlation_to_markdown()` to `formatters/markdown.py`. Add `verification_to_csv()` and `correlation_to_csv()` to `formatters/csv_export.py`. |
| 5.6 | Open | | | Add `verification` and `correlations` CLI subcommands to `cli.py`. Add formatter tests to `test_formatters.py`. |
| 5.7 | Open | | | Add `/verification` and `/correlations` API endpoints to `api.py`. |
| 5.8 | Open | | | Run `pytest` — all tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 5.9 | Open | | | Stage all Phase 5 changes. |
| 5.10 | Open | | | Commit: "Add claim verification and benchmark correlation (Tier 3)". |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add claim verification and benchmark correlation (Tier 3)`

## Phase 6: Digest Integration + Documentation

**Goal:** Weekly digest includes spotlight and evolution highlights. CLAUDE.md updated with new commands and architecture. All tests pass.
**Depends on:** Phases 2, 3, 4, 5.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Modify `ai_benchmark/analysis/services/digest.py`: import and call `get_spotlight` and `get_benchmark_evolution`, populate `spotlight_models` and `evolution_highlights` on DigestReport. |
| 6.2 | Open | | | Extend `digest_to_markdown()` in `formatters/markdown.py` to render spotlight models and evolution highlights sections. |
| 6.3 | Open | | | Update `tests/test_analysis/test_digest.py`: verify digest includes spotlight_models and evolution_highlights fields. |
| 6.4 | Open | | | Update `CLAUDE.md`: add 7 new CLI commands to analysis section, update Analysis Architecture with new service modules and dataclass count, update test count. |
| 6.5 | Open | | | Run `pytest` — all tests pass. Run `ruff check` and `ruff format --check` — clean. |
| 6.6 | Open | | | Stage all Phase 6 changes. |
| 6.7 | Open | | | Commit: "Integrate spotlight and evolution into digest, update documentation". |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Integrate spotlight and evolution into digest, update documentation`
