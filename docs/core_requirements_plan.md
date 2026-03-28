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

### Task 1.1 — Create `pyproject.toml` with dependency groups

Define project metadata, Python 3.12+ requirement. Core deps: `httpx[http2]`, `beautifulsoup4`, `lxml`, `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`, `apscheduler`, `pydantic`, `pydantic-settings`, `structlog`, `click`. Dev deps: `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`. Optional research deps: `pymupdf`, `semanticscholar`.

- **Key file:** `pyproject.toml`
- **State:** Completed
- **Started:** 2026-03-28 10:00 PST
- **Completed:** 2026-03-28 10:05 PST

### Task 1.2 — Create the package structure

All `__init__.py` files and empty module stubs: `ai_benchmark/` with subpackages `config/`, `models/`, `collection/`, `sources/` (with `benchmarks/`, `research/`, `news/`, `community/` sub-packages), `processing/`, `scheduling/`, `reporting/`. Entry points: `main.py`, `cli.py`.

- **Key files:** `ai_benchmark/__init__.py`, `ai_benchmark/main.py`, `ai_benchmark/cli.py`
- **State:** Completed
- **Started:** 2026-03-28 10:00 PST
- **Completed:** 2026-03-28 10:05 PST

### Task 1.3 — Implement Pydantic settings and TOML config loading

`PipelineSettings` model with database URL, log level, user-agent string, request timeout, concurrency limits, proxy config. Load from environment variables with TOML file fallback.

- **Key file:** `ai_benchmark/config/settings.py`
- **State:** Completed
- **Started:** 2026-03-28 10:05 PST
- **Completed:** 2026-03-28 10:10 PST

### Task 1.4 — Define the source catalog in TOML

All 22 sources with metadata fields from `docs/core_requirements.md`: source_name, category, organization, homepage_url, base_domain, trust_rating, source_role, classification, pages (canonical_url, page_type, polling_frequency), collection_method. Pydantic models `SourceConfig` and `PageConfig` to validate the TOML.

- **Key files:** `ai_benchmark/config/sources.toml`, `ai_benchmark/config/settings.py`
- **State:** Completed
- **Started:** 2026-03-28 10:05 PST
- **Completed:** 2026-03-28 10:12 PST

### Task 1.5 — Define SQLAlchemy data models and initial Alembic migration

Models: `Source`, `Page`, `Snapshot` (content + hash + timestamp), `EventRecord` (normalized change event), `ClaimRecord` (claim_text, source_type, confidence_tier, cross_refs), `CrossReference` (link table with relationship_type), `CandidatePaper`, `EnrichedPaper`. Composite unique constraints matching the dedup key: `{normalized_title, organization, source_type, canonical_path_or_slug, published_date}`. Alembic init + first migration.

- **Key files:** `ai_benchmark/models/base.py`, `models/sources.py`, `models/events.py`, `models/research.py`, `alembic/`
- **State:** Completed
- **Started:** 2026-03-28 10:05 PST
- **Completed:** 2026-03-28 10:12 PST

### Task 1.6 — CLI entry point and database init command

Click-based CLI: `init-db` (runs migrations), `run` (stub), `check-config` (validates source catalog TOML). Register as console script in `pyproject.toml`.

- **Key file:** `ai_benchmark/cli.py`
- **State:** Completed
- **Started:** 2026-03-28 10:10 PST
- **Completed:** 2026-03-28 10:14 PST

### Task 1.7 — Structured logging and smoke tests

Configure `structlog` with JSON output, bound context (source_name, page_url). Write smoke tests for config loading and model creation.

- **Key files:** `ai_benchmark/main.py`, `tests/conftest.py`, `tests/test_config.py`
- **State:** Completed
- **Started:** 2026-03-28 10:10 PST
- **Completed:** 2026-03-28 10:15 PST

### Phase 1 Summary

- **Changes:** Created project skeleton with `pyproject.toml`, full package structure (13 sub-packages), Pydantic settings with env-var support, TOML source catalog (22 sources / 48 pages), SQLAlchemy async models (Source, Page, Snapshot, EventRecord, ClaimRecord, CrossReference, CandidatePaper, EnrichedPaper), Alembic migration setup, Click CLI with `init-db`/`check-config`/`run` commands, structlog JSON logging, `.gitignore`, and 8 passing smoke tests. APScheduler pinned to 3.x (4.x is alpha-only).
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 1: Project scaffolding, data model, and configuration"`

---

## Phase 2: Core Collection Engine (Fetch, Diff, Store)

**Goal:** Build the generic HTTP fetcher, HTML diffing engine, and snapshot storage layer. After this phase, you can fetch any URL, store the snapshot, and detect changes on subsequent fetches.

**Depends on:** Phase 1 (database models, config).

### Task 2.1 — Async HTTP fetcher

`Fetcher` class wrapping `httpx.AsyncClient`. Configurable user-agent rotation, request timeout, retry with exponential backoff (3 attempts), concurrency semaphore (default 5), proxy support. Returns `FetchResult` dataclass: status_code, headers, body_text, elapsed_ms, fetched_at. Handles 403 (log + skip), 429 (respect Retry-After), connection errors, timeouts.

- **Key file:** `ai_benchmark/collection/fetcher.py`
- **State:** Completed
- **Started:** 2026-03-28 10:16 PST
- **Completed:** 2026-03-28 10:22 PST

### Task 2.2 — HTML cleaning and text extraction

`clean_html()` strips scripts, styles, nav, footer, ads; extracts main content area; normalizes whitespace. Uses BeautifulSoup + lxml. Configurable CSS selectors per source.

- **Key file:** `ai_benchmark/collection/differ.py`
- **State:** Completed
- **Started:** 2026-03-28 10:16 PST
- **Completed:** 2026-03-28 10:22 PST

### Task 2.3 — HTML diffing engine

`diff_snapshots(old_text, new_text)` returning `DiffResult`: changed (bool), added_lines, removed_lines, change_ratio (float 0–1), diff_html. Semantic layer detects structural changes (new changelog items, new pricing rows, new articles) vs cosmetic noise. Configurable noise threshold (default change_ratio < 0.01).

- **Key file:** `ai_benchmark/collection/differ.py`
- **State:** Completed
- **Started:** 2026-03-28 10:16 PST
- **Completed:** 2026-03-28 10:22 PST

### Task 2.4 — Snapshot storage and comparison

`SnapshotManager`: `store_snapshot(page_id, content, content_hash)`, `get_latest_snapshot(page_id)`, `compare_with_latest(page_id, new_content)`. SHA-256 content hashing for fast no-change detection before running the full differ.

- **Key file:** `ai_benchmark/collection/snapshot.py`
- **State:** Completed
- **Started:** 2026-03-28 10:16 PST
- **Completed:** 2026-03-28 10:22 PST

### Task 2.5 — Base API client for REST sources

`APIClient` base class for JSON API sources. Handles auth headers (Bearer tokens, API keys from config), rate limiting, pagination. Subclassable for Semantic Scholar, GitHub, HF APIs.

- **Key file:** `ai_benchmark/collection/api_client.py`
- **State:** Completed
- **Started:** 2026-03-28 10:16 PST
- **Completed:** 2026-03-28 10:22 PST

### Task 2.6 — Integration tests with fixture HTML

Sample HTML snapshots in `tests/fixtures/` (changelog, pricing, newsroom). Test full fetch → clean → diff → store cycle with `respx` mocks. Verify identical content → `changed=False`, simulated changelog addition → correct diff.

- **Key files:** `tests/test_fetcher.py`, `tests/test_differ.py`, `tests/test_snapshot.py`, `tests/fixtures/`
- **State:** Completed
- **Started:** 2026-03-28 10:22 PST
- **Completed:** 2026-03-28 10:28 PST

### Phase 2 Summary

- **Changes:** Async HTTP fetcher with retry/backoff/429 handling, HTML cleaner (strips noise tags, extracts via CSS selectors), semantic diff engine (text diff + structural change detection), snapshot manager with SHA-256 fast-path, base API client with pagination, 3 HTML fixture files, 16 new tests (24 total passing).
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 2: Core collection engine (fetch, diff, store)"`

---

## Phase 3: Official Vendor Source Integrations (Primary Sources)

**Goal:** Implement collectors for the 7 official vendor sources: OpenAI, Anthropic, Google/Gemini, xAI, Mistral, Cohere, Meta. These are trust-rating 4.5–5, highest-value sources. After this phase, all primary sources produce event records.

**Depends on:** Phase 2 (fetcher, differ, snapshot store).

### Task 3.1 — Abstract SourceCollector base class

Abstract `SourceCollector` with methods: `collect(page)` → raw items, `extract_events(raw_items)` → `EventRecord` candidates, `get_pages()` → page configs. Hooks for source-specific CSS selectors, content extraction, model-name parsing.

- **Key file:** `ai_benchmark/sources/base.py`
- **State:** Completed
- **Started:** 2026-03-28 10:30 PST
- **Completed:** 2026-03-28 10:38 PST

### Task 3.2 — Normalizer for event field extraction

Functions: `normalize_title()`, `extract_model_slug()`, `extract_version()`, `extract_date()`, `classify_event_type()` (model_release, pricing_change, api_update, deprecation, system_card, announcement). Regex patterns for known model families: GPT-*, Claude-*, Gemini-*, Grok-*, Mistral-*, Command-*, Llama-*.

- **Key file:** `ai_benchmark/processing/normalizer.py`
- **State:** Completed
- **Started:** 2026-03-28 10:30 PST
- **Completed:** 2026-03-28 10:38 PST

### Task 3.3 — OpenAI collector

Pages: product newsroom, API changelog, models page, pricing, system cards. Changelog: parse dated entries, extract model slugs. Pricing: parse tables, detect row changes.

- **Key file:** `ai_benchmark/sources/openai.py`
- **State:** Completed
- **Started:** 2026-03-28 10:38 PST
- **Completed:** 2026-03-28 10:45 PST

### Task 3.4 — Anthropic collector

Pages: newsroom, system cards, models overview, pricing, API release notes. System card extraction: parse card index, detect new cards by date.

- **Key file:** `ai_benchmark/sources/anthropic.py`
- **State:** Completed
- **Started:** 2026-03-28 10:38 PST
- **Completed:** 2026-03-28 10:45 PST

### Task 3.5 — Google/Gemini collector

Pages: Gemini release notes, pricing, rate limits, models catalog, DeepMind blog. Handles two domains: `ai.google.dev` and `blog.google`.

- **Key file:** `ai_benchmark/sources/google.py`
- **State:** Completed
- **Started:** 2026-03-28 10:38 PST
- **Completed:** 2026-03-28 10:45 PST

### Task 3.6 — xAI, Mistral, Cohere, Meta collectors

xAI: release notes, models/pricing, news. Mistral: changelog (labeled entries like "MODEL RELEASED"), news, pricing. Cohere: blog, release notes, docs. Meta: GitHub API for `meta-llama` org (releases, repos), open-source AI page.

- **Key files:** `ai_benchmark/sources/xai.py`, `mistral.py`, `cohere.py`, `meta.py`
- **State:** Completed
- **Started:** 2026-03-28 10:38 PST
- **Completed:** 2026-03-28 10:45 PST

### Task 3.7 — Event record persistence

Wire collectors to database: persist `EventRecord` rows linked to source and page. Skip storage if identical event exists by composite key (early dedup).

- **Key files:** `ai_benchmark/sources/persistence.py`, `ai_benchmark/sources/registry.py`
- **State:** Completed
- **Started:** 2026-03-28 10:45 PST
- **Completed:** 2026-03-28 10:48 PST

### Task 3.8 — Tests for vendor collectors

One fixture HTML file per major page type per vendor. Tests that extraction produces correct event records from known HTML.

- **Key files:** `tests/test_sources/test_collectors.py`, `tests/test_sources/test_persistence.py`
- **State:** Completed
- **Started:** 2026-03-28 10:45 PST
- **Completed:** 2026-03-28 10:50 PST

### Phase 3 Summary

- **Changes:** Abstract SourceCollector base class with fetch/diff/extract lifecycle, event field normalizer (model slug extraction for 10 model families with stop-word trimming, date extraction, event type classification), 7 vendor collectors (OpenAI, Anthropic, Google, xAI, Mistral, Cohere, Meta with GitHub API), collector registry, event persistence with composite-key dedup, 22 new tests (46 total passing).
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 3: Official vendor source integrations"`

---

## Phase 4: Benchmark and Research Discovery Integrations

**Goal:** Add collectors for 7 benchmark sources and 3 research feeds. Implement the research triage pipeline (candidate → enrichment → authoritative store). After this phase, 17 of 22 sources are covered.

**Depends on:** Phase 3 (base collector, normalizer, event persistence).

### Task 4.1 — Benchmark base class with variant-aware extraction

`BenchmarkCollector(SourceCollector)` with additional fields: benchmark_family, variant_name, evaluation_conditions. Store leaderboard snapshots as structured data (model, score, rank, conditions), not just raw HTML diffs.

- **Key file:** `ai_benchmark/sources/benchmarks/__init__.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.2 — Artificial Analysis, LMArena, LiveBench collectors

Artificial Analysis: leaderboard (model, score, price, speed), methodology tracking. LMArena: arena tabs, ELO/preference scores. LiveBench: leaderboard, PDF methodology (pymupdf).

- **Key files:** `ai_benchmark/sources/benchmarks/artificial_analysis.py`, `lmarena.py`, `livebench.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.3 — SWE-bench, GAIA, HLE, Terminal-Bench collectors

SWE-bench: variant-aware (Verified, Lite, Full, Pro, Multilingual, Multimodal), contamination flag. GAIA: HF org page, leaderboard Space, results_public. HLE: Scale leaderboard, confidence intervals, slice tracking. Terminal-Bench: leaderboard + registry/version tracking.

- **Key files:** `ai_benchmark/sources/benchmarks/swebench.py`, `gaia.py`, `hle.py`, `terminal_bench.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.4 — arXiv collector

Poll `cs.AI/recent`, `cs.CL/recent`, `cs.LG/recent`. Extract: title, authors, arxiv_id, categories, abstract link, date. Feed into `CandidatePaper` queue. Filter by relevance to tracked models/benchmarks.

- **Key file:** `ai_benchmark/sources/research/arxiv.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.5 — Semantic Scholar API client

Extend `APIClient` for S2 Graph API. Paper search, details (abstract, citations, venue, references), recommendations. Rate limit handling. Used for enrichment, not direct polling.

- **Key file:** `ai_benchmark/sources/research/semantic_scholar.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.6 — Hugging Face Papers collector

Poll `/papers` and `/papers/trending`. Extract: title, upvotes, code links, arxiv links, date. Feed into candidate queue.

- **Key file:** `ai_benchmark/sources/research/hf_papers.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.7 — Research triage pipeline

Three-stage pipeline: (1) Candidate — arXiv/HF Papers discoveries land with status `pending`. (2) Enrichment — call Semantic Scholar, check relevance, set `enriched` or `rejected`. (3) Promotion — relevant papers promoted to `EnrichedPaper` in authoritative store.

- **Key file:** `ai_benchmark/processing/triage.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 4.8 — Tests for benchmark and research collectors

Fixture HTML for benchmark leaderboards and arXiv listings. Test variant name extraction. Test triage pipeline with mock Semantic Scholar responses.

- **Key files:** `tests/test_sources/test_benchmarks/`, `tests/test_sources/test_research/`, `tests/test_triage.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Phase 4 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 4: Benchmark and research discovery integrations"`

---

## Phase 5: News and Community Integrations

**Goal:** Add the final 5 sources: Reuters, TechCrunch, HF Forums, GitHub discovery, HF leaderboard docs. Implement confidence-tier separation for news and minimal-metadata ingestion for community sources. After this phase, all 22 sources are covered.

**Depends on:** Phase 4 (all prior collectors operational).

### Task 5.1 — Reuters collector

Poll `/technology/artificial-intelligence/` and Artificial Intelligencer newsletter pattern. Extract: headline, byline, date, summary, URL. Auto-ingest with high-confidence secondary tier. Polling: every 3–6h.

- **Key file:** `ai_benchmark/sources/news/reuters.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.2 — TechCrunch collector

Poll `/category/artificial-intelligence/`. Extract: headline, author, date, summary, tags. Medium-confidence discovery tier. Flag material claims for confirmation against primary sources.

- **Key file:** `ai_benchmark/sources/news/techcrunch.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.3 — News confidence tier system

Assign `confidence_tier` to news events based on source classification. Reuters: `high_secondary` (auto-ingest, lighter review). TechCrunch: `medium_discovery` (triggers confirmation). Wire into `ClaimRecord` creation.

- **Key file:** `ai_benchmark/processing/normalizer.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.4 — Hugging Face Forums minimal metadata collector

Poll `discuss.huggingface.co` top-level and research/Spaces areas. Ingest only: title, author, timestamp, tags, outbound links. No full content — discovery-only per requirements.

- **Key file:** `ai_benchmark/sources/community/hf_forums.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.5 — GitHub discovery collector

Poll watched orgs (`meta-llama`, `openai`, `anthropics`, `google`, `mistralai`, `cohere-ai`, `xai-org`) via GitHub API. Track: new repos, releases, README changes, tags. Non-official orgs: discovery-only.

- **Key file:** `ai_benchmark/sources/community/github_discovery.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.6 — HF leaderboard docs collector

Poll the HF leaderboard docs index as a meta-source for discovering new community benchmarks.

- **Key file:** `ai_benchmark/sources/benchmarks/__init__.py` (or dedicated collector)
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 5.7 — Full source coverage integration test

Verify all 22 sources have a registered collector. Verify each returns well-formed results against fixture data.

- **Key file:** `tests/test_full_coverage.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Phase 5 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 5: News and community integrations — all 22 sources covered"`

---

## Phase 6: Verification, Deduplication, and Cross-Referencing

**Goal:** Implement the full verification hierarchy, composite-key deduplication, conflict-aware claim storage, and cross-reference table maintenance. This is the intelligence layer that turns raw events into a coherent knowledge base.

**Depends on:** Phase 5 (all 22 sources producing events and claims).

### Task 6.1 — Composite-key deduplicator

`deduplicate(event)` checks against `{normalized_title, organization, source_type, canonical_path_or_slug, published_date}`. For model events, also checks `{model_slug, version_date}`. Returns: `is_duplicate`, `existing_record_id`, `similarity_score`. Near-duplicate detection via fuzzy title matching within same org + date window.

- **Key file:** `ai_benchmark/processing/deduplicator.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 6.2 — Verification hierarchy engine

Implements five verification chains: (1) Model releases — vendor launch > docs > pricing > changelog > system card; confirmed when 2+ official surfaces agree. (2) Benchmark claims — benchmark owner first, then vendor; record variant + conditions. (3) Pricing — confirmed only when official pricing page changes; store snapshot + timestamp. (4) Company announcements — newsroom > docs > Reuters > others. (5) Research — primary paper > Semantic Scholar > company blog; blog alone never confirms.

- **Key file:** `ai_benchmark/processing/verification.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 6.3 — Conflict-preserving claim management

When sources conflict, store both as separate `ClaimRecord` entries with labels: `official_self_report`, `benchmark_owner_report`, `secondary_news_report`, etc. Never merge conflicting claims.

- **Key files:** `ai_benchmark/models/events.py`, `ai_benchmark/processing/verification.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 6.4 — Cross-reference table builder

`link_related_records(event)` scans for related records across sources. Matching: same model_slug within time window, same org + event_type, same arxiv_id. Creates `CrossReference` rows with relationship: `confirms`, `supplements`, `conflicts_with`, `cites`.

- **Key file:** `ai_benchmark/processing/cross_reference.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 6.5 — Post-collection processing pipeline

Wire normalize → deduplicate → verify → cross-reference into the collection flow. Define as a processing pipeline invoked after each collector produces events.

- **Key file:** `ai_benchmark/processing/pipeline.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 6.6 — Verification and dedup tests

Test: same event from two sources deduplicates. Test: model release confirmed when 2 official surfaces agree. Test: conflicting benchmark claims stored separately. Test: cross-references created between related events.

- **Key files:** `tests/test_deduplicator.py`, `tests/test_verification.py`, `tests/test_cross_reference.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Phase 6 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 6: Verification, deduplication, and cross-referencing"`

---

## Phase 7: Scheduling, Orchestration, Reporting, and Documentation

**Goal:** Add the scheduling layer that runs all collectors on defined cadences with concurrency control and error handling. Add query/reporting interface. Update README.md. After this phase, the system is production-ready for continuous operation.

**Depends on:** Phase 6 (complete processing pipeline).

### Task 7.1 — APScheduler integration

Initialize async scheduler. Register each source's pages as jobs with cron triggers matching cadences from `schedules.toml`. SQLite-backed job store for persistence. Configurable concurrency limit (default 5).

- **Key file:** `ai_benchmark/scheduling/scheduler.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.2 — Cadence configuration

`schedules.toml` mapping each source/page to cron expressions. Official changelogs: every 6h. Reuters: every 3–6h. Daily sources: multiple daily windows. `cadence.py`: parse and validate.

- **Key files:** `ai_benchmark/config/schedules.toml`, `ai_benchmark/scheduling/cadence.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.3 — Error handling and health tracking

Per-job: log failures, retry with backoff, circuit breaker after N consecutive failures. Track `last_success_at`, `last_failure_at`, `consecutive_failures` per source/page. Warn on sources failing > 24h.

- **Key file:** `ai_benchmark/scheduling/scheduler.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.4 — CLI commands for operations

`collect` — run one or all collectors immediately. `status` — last collection time, success/failure, event counts per source. `query` — search events by model, org, date, type. `export` — dump to JSON/CSV.

- **Key file:** `ai_benchmark/cli.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.5 — Query and reporting interface

`get_events(filters)`, `get_claims(entity)`, `get_cross_refs(event_id)`, `get_unconfirmed_claims()`, `get_recent_changes(hours=24)`. JSON and CSV export with configurable fields.

- **Key files:** `ai_benchmark/reporting/query.py`, `ai_benchmark/reporting/export.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.6 — Application bootstrap and daemon mode

Wire config loading, database init, scheduler start, signal handling (graceful shutdown). Foreground mode for dev, daemon-style for production.

- **Key file:** `ai_benchmark/main.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.7 — End-to-end integration tests

Test scheduler triggers on cadence. Test full cycle: fetch → diff → extract → normalize → dedup → verify → cross-ref → store. Test graceful shutdown mid-cycle.

- **Key files:** `tests/test_scheduler.py`, `tests/test_e2e.py`
- **State:** Open
- **Started:** —
- **Completed:** —

### Task 7.8 — Update README.md and project documentation

Update `README.md` with: project overview, setup/install instructions, architecture summary, CLI usage, how to add a new source. Update `CLAUDE.md` with build/test/lint commands and development workflow.

- **Key files:** `README.md`, `CLAUDE.md`
- **State:** Open
- **Started:** —
- **Completed:** —

### Phase 7 Summary

- **Changes:** _(fill on completion)_
- **Changes hosted at:** TBD
- **Commit:** `git commit -m "Phase 7: Scheduling, orchestration, reporting, and documentation"`
- **Final commit:** `git commit -m "Update README.md with project documentation"`
