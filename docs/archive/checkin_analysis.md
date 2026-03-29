# Commit Activity Analysis: Component Evolution

**Repository**: ai_benchmark
**Period analyzed**: 2026-03-28 (40 commits)
**Scope**: Full project history from seed to current state

---

## Overview

The repository was built entirely in a single day across eight distinct evolutionary tracks. Each track represents a coherent component that grew from a scaffold to a complete implementation, with later tracks building on the stable foundations laid by earlier ones. The overall shape is a layered pyramid: data collection infrastructure at the base, intelligence processing in the middle, and evaluation tooling at the top — with a cross-cutting quality and compliance pass woven throughout.

---

## Component 1: Core Requirements and Source Pipeline

**Commits**: ~14 (seed + 7 phases, ~13:00–15:13)
**Files at completion**: ~55 files, ~6,000 lines

### Seed

The repository began as a single document (`docs/core_requirements.md`) with no code. This commit established the specification contract that every subsequent phase would fulfill.

### Phase 1 — Scaffold

The structural skeleton appeared in one large commit: SQLAlchemy ORM models (`Source`, `Page`, `Snapshot`, `EventRecord`, `ClaimRecord`, `CrossReference`), a 64-page `sources.toml` catalog spanning 22 sources, a minimal CLI stub, Alembic migration 001, Pydantic settings with the `AI_BENCH_` prefix, and a `pyproject.toml` wiring together the package. This phase defined the data model that every other component reads and writes.

### Phases 2–3 — Collection Engine and Vendor Collectors

The HTTP layer was added next: `httpx`-backed fetcher with exponential backoff, HTML differ, snapshot manager, and a base API client. Immediately following, seven vendor-specific collectors were implemented (OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta) along with the normalizer (title normalization, model slug extraction, confidence-tier mapping) and the collector registry. The registry pattern — a `COLLECTOR_CLASSES` dict mapping org names to collector classes — remained unchanged through all subsequent phases.

### Phases 4–5 — Benchmark, Research, News, and Community Collectors

Seven benchmark collectors (Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE, Terminal-Bench) arrived with the `BenchmarkCollector` base class and `LeaderboardEntry` return type. The research triage pipeline (`CandidatePaper` → `EnrichedPaper`) was introduced alongside arXiv, Semantic Scholar, and HF Papers collectors. News (Reuters, TechCrunch) and community (HF Forums, GitHub discovery, HF Leaderboard Docs) collectors completed source coverage.

### Phases 6–7 — Processing Chain, Scheduling, and Reporting

The intelligence layer closed the loop: a three-strategy deduplicator (exact composite key → model-slug window → fuzzy 0.85), a five-chain verification hierarchy, cross-reference builder with two matching strategies, and the `process_item()` / `process_items()` pipeline orchestrator. APScheduler integration, cron cadence config (`schedules.toml`, 24 entries), and `SourceHealthTracker` with circuit breaker provided the daemon runtime. CLI commands (`collect`, `run`, `status`, `query`, `export`) and JSON/CSV export completed the user-facing surface.

**Evolution pattern**: Requirements document → data shape → HTTP transport → source-specific parsing → intelligence processing → runtime orchestration. Each phase consumed the API of the previous without needing to revise it.

---

## Component 2: Model Evaluation Pipeline

**Commits**: ~9 phases (E1–E9, ~15:47–16:35)
**Files at completion**: ~80 new files, ~9,000 lines in `eval/`

### E1–E2 — Data Models and Services

The eval subsystem opened with its full relational schema in one commit: 15 SQLAlchemy tables (`datasets`, `dataset_versions`, `test_cases`, `scorers`, `scorer_versions`, `evaluation_definitions`, `evaluation_versions`, `machine_profiles`, `machine_snapshots`, `target_configurations`, `run_groups`, `runs`, `run_item_results`, `run_aggregate_metrics`, `artifacts`). Eight async service modules followed, each accepting `AsyncSession` and returning ORM instances. The service pattern established here — convert ORM objects to dicts before `session.commit()` to avoid `MissingGreenlet` — persisted without change.

### E3–E4 — Execution Engine and Scoring

`RunOrchestrator` implemented a three-stage lifecycle: `create_run()` → `execute_run()` → `score_run()`. Four model adapters (OpenAI, Anthropic, LocalAdapter for ollama/vllm/llamacpp, GenericHTTP) provided the inference surface. `ScorerRunner` with weighted pass logic coordinated seven built-in scorers: `exact_match`, `fuzzy_match`, `rubric`, `format_validator`, `latency_cost`, `safety`, `model_judge`.

### E5–E6 — API and CLI

44 FastAPI endpoints under `/api/eval/` with full Pydantic request/response schemas gave the system a REST surface. Eight Click subcommands (`run`, `run-matrix`, `status`, `list`, `compare`, `export`, `rescore`, `serve`) wrapped the services for terminal use.

### E7–E9 — UI, Comparison Views, and Integration Tests

16 Jinja2 templates (dashboard, entity list/detail, run detail with live auto-refresh, comparison view, reports with Chart.js) rendered server-side. Comparison and report services were added as a late-phase concern — notably after the API, suggesting they were treated as analysis features rather than core pipeline features. Integration tests closed the eval track.

**Evolution pattern**: Schema-first → service layer → execution → scoring → API surface → CLI → UI → analytics. The eval component mirrors the source pipeline's layered approach but at a higher level of complexity, reflecting the broader scope of a full evaluation platform.

---

## Component 3: Gap Remediation (v1)

**Commits**: 6 phases (G1–G6, ~17:26–17:52)
**Nature**: Correctness and completeness pass against the requirements spec

### G1–G2 — Schema Extensions and Confidence Mapping

The first gaps closed were structural: `benchmark_variant` and `evaluation_conditions` columns added to `EventRecord`, `snapshot_id` FK added to `ClaimRecord`, `model_slug` included in the deduplication composite key. Confidence-tier mapping and conflict detection (the `conflicted` confirmation status) were formalized in G2.

### G3–G4 — Research Enrichment and Source Catalog Expansion

Semantic Scholar enrichment client and the full triage pipeline (candidate → enrichment → promote/reject) were completed. The source catalog was audited and expanded to ensure all 22 required sources were present with correct page types and polling cadences.

### G5–G6 — Noise Filtering and Discovery Automation

Quality filter (trivial change ratio, stale date detection, garbage title patterns) and HF Forums support-thread filtering reduced ingestion noise. The discovery automation track introduced the `FollowUpTask` ORM model, `discovery_queue.py` with enqueue logic for four task types per new slug, and `path_prober.py` covering 11 path families. The `execute_follow_up_tasks()` function was stubbed — it enqueued correctly but did not dispatch real fetches.

**Evolution pattern**: Structural correctness → semantic correctness → coverage completeness → quality → automation. This track is characteristically reactive — it identified and closed the delta between specification and implementation rather than building net-new capability.

---

## Component 4: PEP8 and Ruff Compliance

**Commits**: 7 phases (P1–P7, ~17:59–18:14)
**Files touched**: 117 files

This track ran orthogonally to all others. It did not add features — it enforced consistent code style across a codebase that had grown quickly across multiple implementation phases.

The progression was: auto-fixable violations (ruff `--fix`) → formatting (`ruff format`) → E501 line-length manual resolutions → `TYPE_CHECKING` blocks (moving type-only imports to avoid circular dependencies) → FastAPI `B008` suppression (`Depends()` in default args) → remaining manual violations → CI enforcement (ruff added to `pyproject.toml` checks).

The large file count (117) reflects that style issues were distributed across every module rather than concentrated. The short wall-clock time (15 minutes) reflects that most fixes were automated. The `TYPE_CHECKING` migration was the most semantically significant change — it resolved circular import risks that would have become latent bugs under certain import orderings.

---

## Component 5: LLM Runner Comparison Platform

**Commits**: 7 of 14 planned phases (phases 1–7, ~18:31–19:05)
**Files added**: ~40 new files under `eval/execution/adapters/` and `eval/`

### Phases 1–3 — Registry and Compatibility Model

The runner comparison platform extended the eval pipeline by treating the inference runtime (Ollama, LM Studio, llama.cpp, MLX, vLLM, SGLang, TensorRT-LLM, OpenVINO GenAI) as a first-class experimental variable. Phases 1–3 established the runner/machine registry with compatibility rules and seed data for all 8 runners and 7 machines (DGX Spark 128 GB, Apple Silicon M4 MBP 64 GB, Mac mini 24 GB, RTX 4070 desktop, ASUS Vivobook S 15 with Intel NPU, GTX 1060 laptop, Raspberry Pi edge).

### Phases 4–5 — Dataset Integration and Matrix Expansion

Eval definitions and datasets were wired to runner targets. The matrix expansion service (`run-matrix` CLI command) allowed a single evaluation to fan out across all compatible runner/machine combinations, producing `model × machine × runner × configuration` result sets.

### Phases 6–7 — Execution Dispatch and Runner Adapters

An 11-state run lifecycle and `RunConstraints` were formalized. Eight runner-specific adapters sharing an OpenAI-compatible base interface completed the execution layer. Snapshot capture (recording actual vs. requested machine/runner) enabled post-hoc analysis of scheduling drift.

**Evolution pattern**: Domain model → compatibility rules → seed data → matrix logic → dispatch lifecycle → adapters. The platform extended the eval component without modifying its core services — it layered on top rather than refactoring.

---

## Component 6: Code Review and Documentation Archival

**Commits**: 1 (a95b449, ~19:06)

A single housekeeping commit archived completed planning documents to `docs/archive/`, added `general_code_review_findings.md` summarizing review observations, and created `general_code_review_plan.md` for tracking follow-up items. This commit marks the boundary between the primary build phase and the remediation/refinement work that followed.

---

## Component 7: Gap Remediation (v2)

**Commits**: 1 large commit (5a264b4, ~20:10) covering 13 tasks

The second gap remediation round closed the remaining delta identified in a fresh comparison of `docs/archive/core_requirements.md` against the running implementation.

### Critical Fixes

**Discovery queue wiring** (the most complex change): `execute_follow_up_tasks()` was rewritten from a stub that marked tasks completed without doing any work into a real dispatch function. The new signature accepts a `Fetcher` instance. `_find_page_for_task()` maps task types to source catalog pages by keyword matching on page type. The function instantiates the correct collector via `COLLECTOR_CLASSES`, fetches the page, filters extracted items by model slug, and routes results through `process_items()`. Tasks reach `completed` status only after successful processing; fetch errors and missing-source cases result in `failed` status.

**Confidence tier vocabulary fix**: `CLAIM_LABELS` in `verification.py` mapped `"secondary"` to `"independent_report"`, which was not part of the five-tier standard vocabulary and would cause downstream queries on `confidence_tier = 'high_secondary'` to miss claims written through `verification.create_claim()`. The value was corrected to `"high_secondary"`. An Alembic migration (007) backfills existing records.

### Source Catalog Expansion (+14 pages, 64 → 78)

Five significant gaps in source coverage were closed: Anthropic's main pricing page (`www.anthropic.com/pricing`), SWE-bench Pro leaderboard, Mistral AI Studio pricing, xAI rate limits, and Artificial Analysis embedded performance leaderboard. LMArena image and vision leaderboard tabs were added. Six benchmark-owner GitHub repositories (SWE-bench, LiveBench, GAIA, HLE/Scale, Terminal-Bench, LMArena arena-hard) were registered for release-page polling at 12h cadence.

### Intelligence Layer Completeness

The `cites` relationship type in `cross_reference.py` was promoted from declared-but-unreachable to a fully implemented path: `_extract_arxiv_ids()` parses IDs from event content, `determine_relationship()` returns `"cites"` when two events share an arXiv ID, and `find_related_by_arxiv_id()` implements strategy 3 in `build_cross_references()`. The HLE collector was rewritten to emit separate `LeaderboardEntry` records per score column (`hle_public`, `hle_text_only`, `hle_calibration`) rather than collapsing all slices into a single `hle_public` variant. Semantic Scholar's `SOURCE_TIER_OVERRIDES` was split into two entries — `"api endpoint"` stays `high_secondary` while `"paper_discovery"` becomes `low_discovery` — correctly modeling the source's dual role.

**Evolution pattern**: Stub → real implementation → vocabulary alignment → coverage → intelligence completeness. This track is the "closing the loop" phase — every change in v2 remediation was a gap between what the specification required and what the implementation delivered.

---

## Cross-Cutting Observations

### Layered construction

The project was built bottom-up and consistently so. The data model preceded the collection engine, the collection engine preceded the processing chain, and the processing chain preceded the scheduling runtime. Each layer was sealed before the next began, which is visible in the git history as clean phase boundaries with minimal backtracking.

### Stub-then-wire pattern

Several components were intentionally stubbed in earlier phases and completed in later ones. The discovery queue's `execute_follow_up_tasks()` was the most prominent: the enqueue logic was correct and complete in G6, but the execution was deferred until v2 remediation. The `cites` relationship type in `cross_reference.py` followed the same pattern — declared in the docstring, implemented much later. This pattern suggests planned technical debt: the scaffolding was placed early to signal intent, with the expectation of completion in a dedicated pass.

### Compliance as a separate track

The PEP8/ruff phase (touching 117 files in 15 minutes) demonstrates that code style was not maintained inline during feature development — it was applied in a single concentrated pass after the primary build. The `TYPE_CHECKING` migration was the highest-value output of this track: it resolved import ordering risks that would have been difficult to find later.

### Eval as a parallel universe

The eval pipeline (`eval/`) is architecturally isolated from the source pipeline. It has its own ORM models, services, adapters, CLI, and UI. The only coupling points are the shared `PipelineSettings` parent class and the shared database connection. This isolation allowed the eval component to evolve at its own pace (E1–E9 in under an hour) without destabilizing the collection pipeline.

### Specification fidelity

Both gap remediation rounds demonstrate strong specification fidelity. The v1 round (G1–G6) closed structural and semantic gaps against the requirements. The v2 round closed coverage and behavioral gaps. The fact that two gap remediation rounds were needed — and that the second round required a fresh re-read of the requirements document — is consistent with the pace of development: the implementation moved faster than the verification loop could close.

---

## Component State Summary

| Component | Phases | Status |
|---|---|---|
| Source pipeline | 7 of 7 | Complete |
| Eval pipeline | E1–E9 (9 of 9) | Complete |
| Gap remediation v1 | G1–G6 (6 of 6) | Complete |
| PEP8/ruff compliance | P1–P7 (7 of 7) | Complete |
| Runner comparison platform | 7 of 14 | In progress |
| Gap remediation v2 | 13 of 13 | Complete |
