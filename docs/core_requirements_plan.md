# AI Benchmark Intelligence Pipeline — Implementation Plan

## Work Queue Instructions

This document is the execution work queue for building the AI benchmark intelligence pipeline. Each phase is a self-contained deliverable. Tasks within a phase may be worked in order or parallelized where dependencies allow.

### State Transitions

```
Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed
```

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the task description. Move back to Started once unblocked.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task in the phase reaches `Completed`, write the **Phase Summary** section at the end of that phase.
3. Stage and commit all changes for the phase: `git add . && git commit -m "Phase N: <short description>"`. **Do not push.**
4. Proceed immediately to the next phase. Velocity is the priority — do not wait for review between phases unless blocked.

### Final Phase Protocol

After the last phase is committed, update `README.md` with the project overview, setup, and architecture summary. Commit that separately: `git commit -m "Update README.md with project documentation"`.

### Server Link Convention

Each phase summary includes a `Changes hosted at:` field. Populate this with the URL to the commit or deployment once the changes are available on the hosting server (e.g., GitHub commit URL). Leave as `TBD` until pushed/deployed.

---

## Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Async HTTP | `httpx[http2]` |
| HTML parsing | `beautifulsoup4` + `lxml` |
| HTML diffing | `difflib` (stdlib) + custom semantic layer |
| Database | SQLite via `aiosqlite` (dev), PostgreSQL-ready via SQLAlchemy |
| ORM | `SQLAlchemy 2.0` (async) + `Alembic` migrations |
| Scheduling | `APScheduler 3.x` (async) |
| Config | TOML (`tomllib`) + `pydantic-settings` |
| CLI | `click` |
| Logging | `structlog` (JSON) |
| Testing | `pytest` + `pytest-asyncio` + `respx` |
| Linting | `ruff` |
| Type checking | `mypy` |

---

## Phase 1: Project Scaffolding, Data Model, and Configuration

**Goal:** Establish the project skeleton with a working database schema, typed configuration, source catalog, and CLI entry point. After this phase, `pip install -e .` works, `python -m ai_benchmark init-db` creates the database, and `python -m ai_benchmark check-config` validates the source catalog.

**Depends on:** Nothing (first phase).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 1.1 | Completed | 2026-03-28 10:00 PST | 2026-03-28 10:05 PST | Create `pyproject.toml` with core/dev/research dependency groups. Key file: `pyproject.toml` |
| 1.2 | Completed | 2026-03-28 10:00 PST | 2026-03-28 10:05 PST | Create full package structure — all `__init__.py` and stubs for `config/`, `models/`, `collection/`, `sources/` (with `benchmarks/`, `research/`, `news/`, `community/`), `processing/`, `scheduling/`, `reporting/`, `main.py`, `cli.py` |
| 1.3 | Completed | 2026-03-28 10:05 PST | 2026-03-28 10:10 PST | Implement Pydantic `PipelineSettings` with env-var support and TOML config loading. Key file: `ai_benchmark/config/settings.py` |
| 1.4 | Completed | 2026-03-28 10:05 PST | 2026-03-28 10:12 PST | Define source catalog in TOML — all 22 sources with metadata, pages, polling frequencies. Pydantic `SourceConfig`/`PageConfig` validation. Key files: `config/sources.toml`, `config/settings.py` |
| 1.5 | Completed | 2026-03-28 10:05 PST | 2026-03-28 10:12 PST | Define SQLAlchemy models (`Source`, `Page`, `Snapshot`, `EventRecord`, `ClaimRecord`, `CrossReference`, `CandidatePaper`, `EnrichedPaper`) with composite unique constraints. Alembic init. Key files: `models/*.py`, `alembic/` |
| 1.6 | Completed | 2026-03-28 10:10 PST | 2026-03-28 10:14 PST | Click CLI: `init-db`, `check-config`, `run` (stub). Register as console script. Key file: `ai_benchmark/cli.py` |
| 1.7 | Completed | 2026-03-28 10:10 PST | 2026-03-28 10:15 PST | Configure `structlog` JSON logging with bound context. Write 8 smoke tests for config and models. Key files: `main.py`, `tests/conftest.py`, `tests/test_config.py` |

### Phase 1 Summary

- **Changes:** Project skeleton with `pyproject.toml`, 13 sub-packages, Pydantic settings, TOML source catalog (22 sources / 48 pages), SQLAlchemy async models, Alembic setup, Click CLI, structlog logging, `.gitignore`, 8 passing tests. APScheduler pinned to 3.x (4.x alpha-only).
- **Changes hosted at:** TBD
- **Commit:** `Phase 1: Project scaffolding, data model, and configuration`

---

## Phase 2: Core Collection Engine (Fetch, Diff, Store)

**Goal:** Build the generic HTTP fetcher, HTML diffing engine, and snapshot storage layer. After this phase, you can fetch any URL, store the snapshot, and detect changes on subsequent fetches.

**Depends on:** Phase 1 (database models, config).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 2.1 | Completed | 2026-03-28 10:16 PST | 2026-03-28 10:22 PST | Async HTTP `Fetcher` — httpx with retry/backoff, concurrency semaphore, 403/429 handling, proxy support. Returns `FetchResult` dataclass. Key file: `collection/fetcher.py` |
| 2.2 | Completed | 2026-03-28 10:16 PST | 2026-03-28 10:22 PST | `clean_html()` — strips noise tags (script/style/nav/footer), extracts main content via configurable CSS selectors, normalizes whitespace. Key file: `collection/differ.py` |
| 2.3 | Completed | 2026-03-28 10:16 PST | 2026-03-28 10:22 PST | `diff_snapshots()` — returns `DiffResult` with added/removed lines, change_ratio, diff_text. `extract_structural_changes()` for DOM-level diffs. Noise threshold 0.01. Key file: `collection/differ.py` |
| 2.4 | Completed | 2026-03-28 10:16 PST | 2026-03-28 10:22 PST | `SnapshotManager` — store/retrieve snapshots, `compare_with_latest()` with SHA-256 fast-path for no-change detection. Key file: `collection/snapshot.py` |
| 2.5 | Completed | 2026-03-28 10:16 PST | 2026-03-28 10:22 PST | Base `APIClient` for REST sources — auth headers, rate limiting, paginated fetching. Subclassable for S2/GitHub/HF. Key file: `collection/api_client.py` |
| 2.6 | Completed | 2026-03-28 10:22 PST | 2026-03-28 10:28 PST | Integration tests with 3 HTML fixtures (changelog v1/v2, pricing). Tests for fetcher, differ, snapshot manager. 16 new tests (24 total). Key files: `tests/test_fetcher.py`, `test_differ.py`, `test_snapshot.py`, `fixtures/` |

### Phase 2 Summary

- **Changes:** Async fetcher with retry/backoff/429, HTML cleaner, semantic diff engine, snapshot manager with SHA-256 fast-path, base API client, 3 fixtures, 16 new tests (24 total).
- **Changes hosted at:** TBD
- **Commit:** `Phase 2: Core collection engine (fetch, diff, store)`

---

## Phase 3: Official Vendor Source Integrations (Primary Sources)

**Goal:** Implement collectors for the 7 official vendor sources: OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta. These are trust-rating 4.5–5, highest-value sources. After this phase, all primary sources produce event records.

**Depends on:** Phase 2 (fetcher, differ, snapshot store).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 3.1 | Completed | 2026-03-28 10:30 PST | 2026-03-28 10:38 PST | Abstract `SourceCollector` base — `collect_page()` with fetch/diff/extract lifecycle, `extract_items()` abstract method, configurable CSS selectors. Key file: `sources/base.py` |
| 3.2 | Completed | 2026-03-28 10:30 PST | 2026-03-28 10:38 PST | Normalizer — `normalize_title()`, `extract_model_slug()` (10 families with stop-word trimming), `extract_date()`, `classify_event_type()`. Key file: `processing/normalizer.py` |
| 3.3 | Completed | 2026-03-28 10:38 PST | 2026-03-28 10:45 PST | OpenAI collector — newsroom, API changelog, models page, pricing extraction. Key file: `sources/openai.py` |
| 3.4 | Completed | 2026-03-28 10:38 PST | 2026-03-28 10:45 PST | Anthropic collector — newsroom, system cards, models overview, pricing, API release notes. Key file: `sources/anthropic.py` |
| 3.5 | Completed | 2026-03-28 10:38 PST | 2026-03-28 10:45 PST | Google/Gemini collector — release notes, pricing, models catalog, DeepMind blog. Handles `ai.google.dev` + `blog.google`. Key file: `sources/google.py` |
| 3.6 | Completed | 2026-03-28 10:38 PST | 2026-03-28 10:45 PST | xAI, Mistral, Cohere, Meta collectors — release notes, pricing, news, GitHub API for `meta-llama` org. Key files: `sources/xai.py`, `mistral.py`, `cohere.py`, `meta.py` |
| 3.7 | Completed | 2026-03-28 10:45 PST | 2026-03-28 10:48 PST | Event persistence — `persist_events()` converts `RawItem` → `EventRecord`, skips duplicates by composite key. Collector registry. Key files: `sources/persistence.py`, `sources/registry.py` |
| 3.8 | Completed | 2026-03-28 10:45 PST | 2026-03-28 10:50 PST | Vendor collector tests — normalizer tests, extraction tests per vendor, registry tests, persistence dedup tests. 22 new tests (46 total). Key files: `tests/test_sources/test_collectors.py`, `test_persistence.py` |

### Phase 3 Summary

- **Changes:** SourceCollector base, normalizer (10 model families), 7 vendor collectors (OpenAI, Anthropic, Google, xAI, Mistral, Cohere, Meta+GitHub), registry, event persistence with dedup, 22 new tests (46 total).
- **Changes hosted at:** TBD
- **Commit:** `Phase 3: Official vendor source integrations`

---

## Phase 4: Benchmark and Research Discovery Integrations

**Goal:** Add collectors for 7 benchmark sources and 3 research feeds. Implement the research triage pipeline (candidate → enrichment → authoritative store). After this phase, 17 of 22 sources are covered.

**Depends on:** Phase 3 (base collector, normalizer, event persistence).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 4.1 | Open | — | — | `BenchmarkCollector(SourceCollector)` base with `LeaderboardEntry` dataclass — variant_name, evaluation_conditions, structured leaderboard extraction. Key file: `sources/benchmarks/__init__.py` |
| 4.2 | Open | — | — | Artificial Analysis, LMArena, LiveBench collectors — leaderboard scraping, methodology tracking, PDF parsing. Key files: `sources/benchmarks/artificial_analysis.py`, `lmarena.py`, `livebench.py` |
| 4.3 | Open | — | — | SWE-bench (variant-aware: Verified/Lite/Full/Pro/Multilingual/Multimodal, contamination flag), GAIA (HF org + leaderboard), HLE (confidence intervals, slice tracking), Terminal-Bench (registry). Key files: `sources/benchmarks/swebench.py`, `gaia.py`, `hle.py`, `terminal_bench.py` |
| 4.4 | Open | — | — | arXiv collector — poll `cs.AI/CL/LG/recent`, extract title/authors/arxiv_id, relevance keyword filter, feed to `CandidatePaper` queue. Key file: `sources/research/arxiv.py` |
| 4.5 | Open | — | — | Semantic Scholar API client — paper search, details, recommendations via Graph API. Rate limit handling. Enrichment only. Key file: `sources/research/semantic_scholar.py` |
| 4.6 | Open | — | — | HF Papers collector — poll `/papers` and `/papers/trending`, extract title/upvotes/code links/arxiv links, feed to candidate queue. Key file: `sources/research/hf_papers.py` |
| 4.7 | Open | — | — | Research triage pipeline — 3 stages: (1) Candidate ingestion, (2) Semantic Scholar enrichment + relevance scoring, (3) Promotion to `EnrichedPaper`. Key file: `processing/triage.py` |
| 4.8 | Open | — | — | Benchmark and research tests — fixture HTML for leaderboards and arXiv, variant extraction tests, triage pipeline with mock S2 responses. Key files: `tests/test_sources/test_benchmarks/`, `test_research/`, `test_triage.py` |

### Phase 4 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Phase 4: Benchmark and research discovery integrations`

---

## Phase 5: News and Community Integrations

**Goal:** Add the final 5 sources: Reuters, TechCrunch, HF Forums, GitHub discovery, HF leaderboard docs. Implement confidence-tier separation for news and minimal-metadata ingestion for community sources. After this phase, all 22 sources are covered.

**Depends on:** Phase 4 (all prior collectors operational).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 5.1 | Open | — | — | Reuters collector — poll `/technology/artificial-intelligence/`, Artificial Intelligencer newsletter. High-confidence secondary tier. 3–6h polling. Key file: `sources/news/reuters.py` |
| 5.2 | Open | — | — | TechCrunch collector — poll AI category. Medium-confidence discovery tier. Flag material claims for confirmation. Key file: `sources/news/techcrunch.py` |
| 5.3 | Open | — | — | News confidence tier system — assign `confidence_tier` per source classification (`high_secondary`, `medium_discovery`). Wire into `ClaimRecord`. Key file: `processing/normalizer.py` |
| 5.4 | Open | — | — | HF Forums minimal metadata collector — title, author, timestamp, tags, outbound links only. Discovery-only per requirements. Key file: `sources/community/hf_forums.py` |
| 5.5 | Open | — | — | GitHub discovery collector — poll watched orgs via API. Track new repos, releases, README changes, tags. Key file: `sources/community/github_discovery.py` |
| 5.6 | Open | — | — | HF leaderboard docs collector — poll leaderboard docs index as meta-source for new community benchmarks. Key file: `sources/benchmarks/__init__.py` or dedicated |
| 5.7 | Open | — | — | Full source coverage integration test — verify all 22 sources registered, each returns well-formed results against fixtures. Key file: `tests/test_full_coverage.py` |

### Phase 5 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Phase 5: News and community integrations — all 22 sources covered`

---

## Phase 6: Verification, Deduplication, and Cross-Referencing

**Goal:** Implement the full verification hierarchy, composite-key deduplication, conflict-aware claim storage, and cross-reference table maintenance. This is the intelligence layer that turns raw events into a coherent knowledge base.

**Depends on:** Phase 5 (all 22 sources producing events and claims).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 6.1 | Open | — | — | Composite-key deduplicator — check `{normalized_title, org, source_type, path, date}` + `{model_slug, version_date}`. Fuzzy near-duplicate detection. Key file: `processing/deduplicator.py` |
| 6.2 | Open | — | — | Verification hierarchy engine — 5 chains: model releases (2+ surfaces), benchmark claims (owner first), pricing (page change only), announcements (newsroom > docs > Reuters), research (paper > S2 > blog). Key file: `processing/verification.py` |
| 6.3 | Open | — | — | Conflict-preserving claim management — separate `ClaimRecord` entries with labels (`official_self_report`, `benchmark_owner_report`, etc.). Never merge conflicts. Key files: `models/events.py`, `processing/verification.py` |
| 6.4 | Open | — | — | Cross-reference table builder — match by model_slug + time window, org + event_type, arxiv_id. Relationship types: `confirms`, `supplements`, `conflicts_with`, `cites`. Key file: `processing/cross_reference.py` |
| 6.5 | Open | — | — | Post-collection processing pipeline — wire normalize → dedup → verify → cross-ref after each collector run. Key file: `processing/pipeline.py` |
| 6.6 | Open | — | — | Verification and dedup tests — duplicate detection, 2-surface confirmation, conflict preservation, cross-reference creation. Key files: `tests/test_deduplicator.py`, `test_verification.py`, `test_cross_reference.py` |

### Phase 6 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Phase 6: Verification, deduplication, and cross-referencing`

---

## Phase 7: Scheduling, Orchestration, Reporting, and Documentation

**Goal:** Add the scheduling layer that runs all collectors on defined cadences with concurrency control and error handling. Add query/reporting interface. Update README.md. After this phase, the system is production-ready for continuous operation.

**Depends on:** Phase 6 (complete processing pipeline).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| 7.1 | Open | — | — | APScheduler integration — async scheduler, cron triggers per page from `schedules.toml`, SQLite-backed job store, configurable concurrency. Key file: `scheduling/scheduler.py` |
| 7.2 | Open | — | — | Cadence configuration — `schedules.toml` mapping sources to cron expressions (changelogs 6h, Reuters 3–6h, daily sources). Parse and validate. Key files: `config/schedules.toml`, `scheduling/cadence.py` |
| 7.3 | Open | — | — | Error handling and health tracking — per-job retry with backoff, circuit breaker, `last_success_at`/`last_failure_at`/`consecutive_failures` tracking, 24h failure warnings. Key file: `scheduling/scheduler.py` |
| 7.4 | Open | — | — | CLI operations — `collect` (run one/all immediately), `status` (per-source health), `query` (search events), `export` (JSON/CSV dump). Key file: `ai_benchmark/cli.py` |
| 7.5 | Open | — | — | Query and reporting — `get_events()`, `get_claims()`, `get_cross_refs()`, `get_unconfirmed_claims()`, `get_recent_changes()`. JSON/CSV export. Key files: `reporting/query.py`, `reporting/export.py` |
| 7.6 | Open | — | — | Application bootstrap and daemon mode — wire config, db init, scheduler start, graceful shutdown signal handling. Key file: `ai_benchmark/main.py` |
| 7.7 | Open | — | — | End-to-end integration tests — scheduler cadence triggers, full pipeline cycle, graceful shutdown mid-cycle. Key files: `tests/test_scheduler.py`, `tests/test_e2e.py` |
| 7.8 | Open | — | — | Update `README.md` (overview, setup, architecture, CLI, adding sources) and `CLAUDE.md` (build/test/lint commands, dev workflow). Key files: `README.md`, `CLAUDE.md` |

### Phase 7 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `Phase 7: Scheduling, orchestration, reporting, and documentation`
- **Final commit:** `Update README.md with project documentation`
