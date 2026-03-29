# Core Requirements Gap Remediation — Implementation Plan

**Source document:** `docs/requirements_gap_analysis.md` (23 gaps: 4 critical, 6 high, 13 medium)

## Work Queue Instructions

This document is the execution work queue for remediating all gaps identified in the core requirements gap analysis. Each phase is a self-contained deliverable. Tasks within a phase may be worked in order or parallelized where dependencies allow.

### State Transitions

```
Open  ──>  Started  ──>  Completed
              |
              └──>  Blocked  ──>  Started  ──>  Completed
```

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the task description. Move back to Started once unblocked.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task in the phase reaches `Completed`, write the **Phase Summary** section at the end of that phase.
3. Stage and commit all changes for the phase: `git add . && git commit -m "Gap Phase GN: <short description>"`. **Do not push.**
4. Proceed immediately to the next phase. Velocity is the priority — do not wait for review between phases unless blocked.

### Final Phase Protocol

After the last phase is committed, update `README.md` and `CLAUDE.md` with gap remediation notes. Commit that separately.

### Server Link Convention

Each phase summary includes a `Changes hosted at:` field. Populate with the URL to the commit or deployment once available. Leave as `TBD` until pushed/deployed.

---

## Technology Stack (Additive)

No new dependencies required. All changes use the existing stack: SQLAlchemy async, Alembic, BeautifulSoup, httpx, structlog, pytest + pytest-asyncio.

---

## Phase G1: Schema Extensions and Migration

**Goal:** Extend `EventRecord` with benchmark variant and evaluation conditions fields, add a `snapshot_id` foreign key to `ClaimRecord` for pricing audit trails, and incorporate `model_slug` into the deduplication composite key. After this phase, the schema supports all data that was previously lost in transit, and Alembic can migrate existing databases forward.

**Depends on:** Existing Phase 1 infrastructure (Base, Alembic, event/claim models). Must precede G2 because verification and claim metadata changes depend on the new `ClaimRecord.snapshot_id` column.

**Gaps addressed:** #3 (pricing snapshots not linked to claims), #4 (benchmark variant data lost), #18 (model_slug not in dedup key).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G1.1 | Completed | 2026-03-28 17:00 PST | 2026-03-28 17:01 PST | Add `benchmark_variant: Mapped[str | None] = mapped_column(String(100), nullable=True)` and `evaluation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)` to `EventRecord` in `ai_benchmark/models/events.py`. |
| G1.2 | Completed | 2026-03-28 17:01 PST | 2026-03-28 17:02 PST | Add `snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id"), nullable=True)` to `ClaimRecord` in `ai_benchmark/models/events.py`. Add `snapshot: Mapped[Snapshot | None] = relationship()` back-reference. Use string reference to avoid circular import. |
| G1.3 | Completed | 2026-03-28 17:02 PST | 2026-03-28 17:02 PST | Update the `uq_event_composite_key` unique constraint on `EventRecord` in `ai_benchmark/models/events.py` to include `model_slug` as the 6th field: `("normalized_title", "organization", "source_type", "canonical_path", "published_date", "model_slug")`. |
| G1.4 | Completed | 2026-03-28 17:02 PST | 2026-03-28 17:03 PST | Update `find_exact_duplicate()` in `ai_benchmark/processing/deduplicator.py` to include `model_slug` in the composite-key query. Add `model_slug: str | None` parameter. When `model_slug` is provided, add it to the WHERE clause; when None, filter for NULL. |
| G1.5 | Completed | 2026-03-28 17:03 PST | 2026-03-28 17:03 PST | Update the call to `find_exact_duplicate()` in `is_duplicate()` within `ai_benchmark/processing/deduplicator.py` to pass `model_slug` through. |
| G1.6 | Completed | 2026-03-28 17:03 PST | 2026-03-28 17:04 PST | Update `BenchmarkCollector.extract_items()` in `ai_benchmark/sources/benchmarks/__init__.py` to propagate `variant` and `conditions` from `LeaderboardEntry` into `RawItem.metadata["benchmark_variant"]` and `RawItem.metadata["evaluation_conditions"]`. |
| G1.7 | Completed | 2026-03-28 17:04 PST | 2026-03-28 17:04 PST | Update `process_item()` in `ai_benchmark/processing/pipeline.py` to read `item.metadata.get("benchmark_variant")` and `item.metadata.get("evaluation_conditions")` and set them on the `EventRecord` constructor. |
| G1.8 | Completed | 2026-03-28 17:04 PST | 2026-03-28 17:05 PST | Create Alembic migration `alembic/versions/003_gap_schema_extensions.py` — add `benchmark_variant` and `evaluation_conditions` columns to `event_records`, add `snapshot_id` FK column to `claim_records`, drop and recreate `uq_event_composite_key` with `model_slug` included. |
| G1.9 | Completed | 2026-03-28 17:05 PST | 2026-03-28 17:06 PST | Write tests in `tests/test_gap_g1_schema.py` — 9 tests: EventRecord round-trips benchmark_variant and evaluation_conditions, ClaimRecord.snapshot_id FK roundtrip, unique constraint allows different model_slugs, rejects true duplicates, find_exact_duplicate matches/mismatches on model_slug, process_item populates benchmark_variant from metadata. |
| G1.10 | Completed | 2026-03-28 17:06 PST | 2026-03-28 17:07 PST | Run full test suite: 304 passed, 2 pre-existing CLI test failures unrelated to schema changes. No regressions. |

### Phase G1 Summary

- **Changes:** Extended `EventRecord` with `benchmark_variant` and `evaluation_conditions` fields. Added `snapshot_id` FK and `snapshot` relationship to `ClaimRecord`. Expanded composite unique constraint to include `model_slug` (6-field key). Updated `find_exact_duplicate()` and `is_duplicate()` in deduplicator to include `model_slug` in composite-key queries. Updated `BenchmarkCollector.extract_items()` to propagate variant/conditions metadata. Updated `process_item()` in pipeline to set `benchmark_variant` and `evaluation_conditions` on EventRecord. Created Alembic migration `003_gap_schema_extensions.py`. Added 9 tests in `test_gap_g1_schema.py`. Full suite: 306 tests (304 passed, 2 pre-existing failures).
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G1: Schema extensions — benchmark_variant, snapshot_id FK, model_slug in dedup key`

---

## Phase G2: Confidence Tiers, Verification Chain Enforcement, and Claim Metadata

**Goal:** Expand the confidence tier mapping from 3 to 5 tiers with source-specific overrides, enforce verification chain ordering in `check_confirmation()`, implement conflict relationship detection in cross-references, propagate `page_title` through the pipeline into claims, and link pricing snapshots to claims. After this phase, the verification hierarchy is semantically meaningful rather than decorative.

**Depends on:** G1 (`ClaimRecord.snapshot_id` must exist before pricing snapshot linking can be implemented).

**Gaps addressed:** #5 (confidence tier mapping incomplete), #7 (verification chain not enforced), #11 (page_title missing on claims), #17 (conflict relationships not used).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G2.1 | Open | | | Replace `CONFIDENCE_TIERS` dict in `ai_benchmark/processing/normalizer.py` with a 5-tier mapping. Add `"benchmark_owner": "benchmark_owner_report"` and `"news_medium": "medium_discovery"`. Retain `"primary" -> "official_self_report"`, retain `"secondary" -> "high_secondary"`, retain `"discovery-only" -> "low_discovery"`. |
| G2.2 | Open | | | Create a `SOURCE_TIER_OVERRIDES` dict in `ai_benchmark/processing/normalizer.py` that maps `(organization, source_type)` tuples to specific tiers. Examples: `("Reuters", "news_index") -> "high_secondary"`, `("TechCrunch", "news_index") -> "medium_discovery"`. All benchmark sources with `classification="secondary"` and `page_type` containing `"leaderboard"` -> `"benchmark_owner_report"`. |
| G2.3 | Open | | | Update `confidence_tier_for_classification()` in `ai_benchmark/processing/normalizer.py` to accept optional `organization` and `source_type` parameters. Check `SOURCE_TIER_OVERRIDES` first, then fall back to `CONFIDENCE_TIERS`. |
| G2.4 | Open | | | Update both call sites of `confidence_tier_for_classification()` in `ai_benchmark/processing/pipeline.py` to pass `organization` and `source_type`. |
| G2.5 | Open | | | Rewrite `check_confirmation()` in `ai_benchmark/processing/verification.py` to enforce chain ordering. For `model_release`: require claims from at least 2 distinct source types that appear in `VERIFICATION_CHAINS["model_release"]`, with the highest-priority claim from a source type ranked in the top 3 of the chain. For `benchmark_result`: require a claim with `confidence_tier == "benchmark_owner_report"`. For `pricing_change`: require a claim from a pricing page source. For `announcement`: require newsroom + 1 other. For `research_claim`: require a `primary_paper` claim. |
| G2.6 | Open | | | Add `conflicts_with` relationship detection to `determine_relationship()` in `ai_benchmark/processing/cross_reference.py`. When two events share the same `model_slug` and `event_type` but have different `organization` values and numerical values extracted from `raw_content` differ by >10%, return `"conflicts_with"`. Replace the string-similarity conflict detection in `update_confirmation_status()` in `verification.py` with a new helper `detect_claim_conflict(claim_a, claim_b) -> bool` that compares extracted numerical values rather than string ratios. |
| G2.7 | Open | | | Add `page_title: str | None = None` field to `RawItem` in `ai_benchmark/sources/base.py`. In `SourceCollector.collect_page()`, after extracting items, set `item.page_title = page.page_type` for each item if not already set. |
| G2.8 | Open | | | Update `process_item()` in `ai_benchmark/processing/pipeline.py` to pass `page_title=item.page_title` to both `create_claim()` calls. The `create_claim()` function in `verification.py` already accepts `page_title` as a kwarg — it just needs to be called with it. |
| G2.9 | Open | | | Implement pricing snapshot linking in `ai_benchmark/processing/pipeline.py`. After event creation, if `event_type == "pricing_change"` and `page_id` is not None, query `SnapshotManager.get_latest_snapshot(page_id)` and set `claim.snapshot_id = snapshot.id` on the claim. |
| G2.10 | Open | | | Write tests in `tests/test_verification.py` — test chain-ordered confirmation for model releases (2 high-rank sources confirm, 2 low-rank sources do not), test benchmark confirmation requires `benchmark_owner_report` tier, test conflict detection with numerical disagreement, test that `page_title` propagates from `RawItem` through to `ClaimRecord`. |
| G2.11 | Open | | | Write tests in `tests/test_cross_reference.py` — test `determine_relationship()` returns `"conflicts_with"` when model scores disagree across orgs, test it still returns `"confirms"` for same-model different-source-type. |

### Phase G2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G2: 5-tier confidence mapping, verification chain enforcement, conflict detection, claim metadata`

---

## Phase G3: Research Triage Integration

**Goal:** Create a proper `SemanticScholarCollector` class and register it, route arXiv and HF Papers items through the triage pipeline instead of direct event creation, add relevance filtering to `HFPapersCollector`, and add a scheduled retry job for failed enrichment. After this phase, research papers flow through `ingest_candidate -> enrich_candidate -> promote_to_enriched` before entering the authoritative event store.

**Depends on:** G1 (schema must be stable). Independent of G2.

**Gaps addressed:** #1 (Semantic Scholar has no collector), #2 (research papers bypass triage), #23 (no enrichment retry).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G3.1 | Open | | | Create `SemanticScholarCollector(SourceCollector)` in `ai_benchmark/sources/research/semantic_scholar.py` alongside the existing `SemanticScholarClient`. The collector wraps the client: `extract_items()` returns an empty list (API-only source). Add `async collect_via_api()` method that calls `client.search_paper()` with configured queries and returns `RawItem` objects with `item_type="candidate_paper"`. |
| G3.2 | Open | | | Register `"Semantic Scholar": SemanticScholarCollector` in `COLLECTOR_CLASSES` in `ai_benchmark/sources/registry.py`. Update the import block. |
| G3.3 | Open | | | Add relevance filtering to `HFPapersCollector.extract_items()` in `ai_benchmark/sources/research/hf_papers.py`. After extracting each item, check `any(kw in combined_text.lower() for kw in RELEVANCE_KEYWORDS)` and skip items that match zero keywords. Mirror the pattern used in `ArxivCollector`. Reuse keywords from `ai_benchmark/processing/triage.py`. |
| G3.4 | Open | | | Create `route_research_item()` function in `ai_benchmark/processing/pipeline.py`. This function accepts a `RawItem` with `item_type == "candidate_paper"` and calls `triage.ingest_candidate()` instead of the normal event-creation flow. Extract `arxiv_id`, `authors`, and `categories` from `item.metadata`. |
| G3.5 | Open | | | Update `process_item()` in `ai_benchmark/processing/pipeline.py` to check `item.item_type` early: if `item.item_type == "candidate_paper"`, call `route_research_item()` and return `None` (no EventRecord created directly). This gates arXiv and HF Papers items into the triage pipeline. |
| G3.6 | Open | | | Add `enrich_pending_candidates()` async function in `ai_benchmark/processing/triage.py` that calls `get_pending_candidates()`, iterates them, and calls `enrich_candidate()` for each. If enrichment succeeds (`status == "enriched"`), call `promote_to_enriched()`. This is the scheduled job entry point. |
| G3.7 | Open | | | Add a schedule entry in `ai_benchmark/config/schedules.toml` for the enrichment retry job: `organization = "Semantic Scholar"`, `cron = "0 */4 * * *"` (every 4 hours), `max_concurrent = 1`. |
| G3.8 | Open | | | Add `retry_count: Mapped[int] = mapped_column(Integer, default=0)` and `last_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)` columns to `CandidatePaper` in `ai_benchmark/models/research.py`. Update `enrich_candidate()` in `triage.py` to increment `retry_count` on failure and set `last_retry_at`. Skip candidates with `retry_count >= 3`. |
| G3.9 | Open | | | Add columns from G3.8 to Alembic migration: extend `003_gap_schema_extensions.py` or create new migration `004_research_retry_columns.py`. |
| G3.10 | Open | | | Write tests in `tests/test_triage.py` — test that `route_research_item()` creates a `CandidatePaper` not an `EventRecord`, test HF Papers relevance filtering rejects irrelevant items, test `enrich_pending_candidates()` processes pending papers and promotes relevant ones, test retry limit (3 failures -> paper is skipped). |
| G3.11 | Open | | | Write tests in `tests/test_sources/test_semantic_scholar.py` — test `SemanticScholarCollector` instantiation, test it is retrievable via `get_collector()` with `organization="Semantic Scholar"`, test `collect_via_api()` returns `RawItem` objects with correct `item_type`. |

### Phase G3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G3: Research triage integration — SemanticScholarCollector, paper routing, enrichment retry`

---

## Phase G4: Source Catalog Expansion

**Goal:** Add all missing pages and schedule entries to configuration, enable disabled extractors, and add new page-type handlers for sources that need them. After this phase, all 22 sources are fully configured with every required page from the core requirements.

**Depends on:** G1 (`benchmark_variant` field must exist for SWE-bench variants to be stored). Independent of G2 and G3.

**Gaps addressed:** #6 (SWE-bench only monitors Verified), #8 (Cohere missing pages), #12 (Google missing rate limits), #13 (OpenAI missing system cards), #14 (Artificial Analysis methodology disabled), #15 (LMArena tabs not monitored), #16 (HLE missing Scale hub), #19 (Reuters newsletter URL missing), #22 (GitHub missing xAI and Cohere orgs).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G4.1 | Open | | | Add 4 SWE-bench variant pages to `ai_benchmark/config/sources.toml` under the existing SWE-bench source: `https://www.swebench.com/lite.html`, `https://www.swebench.com/full.html`, `https://www.swebench.com/multilingual.html`, `https://www.swebench.com/multimodal.html`. Set `page_type = "leaderboard"`, `polling_frequency = "daily"`. |
| G4.2 | Open | | | Add Cohere pricing and model docs pages to `ai_benchmark/config/sources.toml` under the existing Cohere source: `https://cohere.com/pricing` with `page_type = "pricing"`, `polling_frequency = "daily"` and `https://docs.cohere.com/docs/models` with `page_type = "model catalog"`, `polling_frequency = "daily"`. |
| G4.3 | Open | | | Add `_extract_pricing()` and `_extract_model_docs()` methods to `CohereCollector` in `ai_benchmark/sources/cohere.py`. Update `extract_items()` to dispatch to these new methods based on `page.page_type`. Follow the pattern from `OpenAICollector._extract_pricing()`. |
| G4.4 | Open | | | Add Google rate limits page to `ai_benchmark/config/sources.toml` under the Google source: `https://ai.google.dev/gemini-api/docs/rate-limits` with `page_type = "rate limits"`, `polling_frequency = "daily"`. Add `_extract_rate_limits()` method to `GoogleCollector` in `ai_benchmark/sources/google.py`. |
| G4.5 | Open | | | Add OpenAI system cards page to `ai_benchmark/config/sources.toml`: a system cards index URL with `page_type = "system-card index"`, `polling_frequency = "daily"`. Add `_extract_system_cards()` method to `OpenAICollector` in `ai_benchmark/sources/openai.py`. Update `extract_items()` to dispatch on `"system" in page.page_type`. |
| G4.6 | Open | | | Enable Artificial Analysis methodology extraction. In `ai_benchmark/sources/benchmarks/artificial_analysis.py`, replace line 18 (`if "methodology" in page.page_type: return []`) with extraction logic: parse methodology description text, extract key metrics and criteria into `RawItem` objects with `item_type = "methodology_description"`. |
| G4.7 | Open | | | Add LMArena arena tab pages to `ai_benchmark/config/sources.toml` under the LMArena source. Add pages for expert, hard-prompts, coding, math, and longer-query tabs. Set `page_type = "leaderboard"`, `polling_frequency = "6h"`. |
| G4.8 | Open | | | Add Scale leaderboard hub to `ai_benchmark/config/sources.toml` under the HLE source: `https://scale.com/leaderboard` with `page_type = "leaderboard hub"`, `polling_frequency = "daily"`. |
| G4.9 | Open | | | Add Reuters newsletter URL to `ai_benchmark/config/sources.toml` under the Reuters source: add the Artificial Intelligencer newsletter archive URL with `page_type = "newsletter"`, `polling_frequency = "daily"`. |
| G4.10 | Open | | | Add xAI and Cohere GitHub org pages to `ai_benchmark/config/sources.toml` under the GitHub source: `https://github.com/xai-org` and `https://github.com/cohere-ai` with `page_type = "github org"`, `polling_frequency = "12h"`. |
| G4.11 | Open | | | Add corresponding schedule entries to `ai_benchmark/config/schedules.toml` for all new pages where the source organization already has an entry. Verify existing cron expressions cover the new pages or add new entries as needed. |
| G4.12 | Open | | | Write tests in `tests/test_config.py` — verify `sources.toml` contains all expected pages: 5 SWE-bench pages, 4 Cohere pages, 5 Google pages, 5 OpenAI pages, 6 LMArena pages, 2 HLE/Scale pages, 2 Reuters pages, 6 GitHub org pages. Verify total page count. Test that `ArtificialAnalysisCollector.extract_leaderboard()` no longer returns `[]` for methodology pages. |

### Phase G4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G4: Source catalog expansion — all missing pages, extractors, and schedule entries`

---

## Phase G5: Noise Filtering and Pipeline Quality

**Goal:** Add community forum support thread filtering and implement low-value page filtering with date validation and change-ratio thresholds. After this phase, the pipeline rejects noise at ingestion rather than relying entirely on downstream deduplication.

**Depends on:** G2 (confidence tier improvements help gate noise). Can proceed in parallel with G4 if needed.

**Gaps addressed:** #20 (community forum support thread filtering), #21 (low-value page filtering).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G5.1 | Open | | | Define `SUPPORT_THREAD_PATTERNS` list in `ai_benchmark/sources/community/hf_forums.py` — regex patterns matching support/help thread titles: `r"\bhow (do|can|to)\b"`, `r"\bhelp\b.*\b(run|install|setup|configure)\b"`, `r"\berror\b"`, `r"\bbug\b"`, `r"\bnot working\b"`, `r"\bcan't\b.*\b(run|install|load)\b"`. |
| G5.2 | Open | | | Add filtering logic to `HFForumsCollector.extract_items()` in `ai_benchmark/sources/community/hf_forums.py`. After extracting each topic title, check against `SUPPORT_THREAD_PATTERNS`. If any pattern matches (case-insensitive), skip the topic. Log skipped topics at debug level. |
| G5.3 | Open | | | Create `ai_benchmark/processing/quality_filter.py` with `is_low_value_page(diff, items, page, times_polled) -> bool`. Criteria: (a) `diff.change_ratio < 0.01` and `times_polled > 5` (stable page, trivial change), (b) no items contain any date within the last 90 days (stale content), (c) all extracted titles are shorter than 5 characters (garbage extraction). |
| G5.4 | Open | | | Add `has_recent_date(items, max_age_days=90) -> bool` helper in `ai_benchmark/processing/quality_filter.py`. Checks `item.date_text` for each item, parses via `normalizer.extract_date()`, returns True if at least one item has a date within the threshold. |
| G5.5 | Open | | | Integrate `is_low_value_page()` into `SourceCollector.collect_page()` in `ai_benchmark/sources/base.py`. After `items = self.extract_items(...)`, call `is_low_value_page(diff, items, page, page.times_polled)`. If True, log a warning and return `([], diff)` — discarding the low-value items. |
| G5.6 | Open | | | Add `times_polled: Mapped[int] = mapped_column(default=0)` column to `Page` in `ai_benchmark/models/sources.py`. Increment it in `SnapshotManager.compare_with_latest()` in `ai_benchmark/collection/snapshot.py` each time a page is polled. |
| G5.7 | Open | | | Add `times_polled` column to the Alembic migration: extend existing migration or create `005_quality_filter_columns.py`. |
| G5.8 | Open | | | Write tests in `tests/test_sources/test_hf_forums.py` — test that support thread titles like "How do I run Llama 3?" and "Error loading model weights" are filtered out, while "Announcing new Llama 3.1 benchmarks" passes through. |
| G5.9 | Open | | | Write tests in `tests/test_quality_filter.py` — test `is_low_value_page()` returns True for trivial-change stable pages, returns True for all-stale-date pages, returns False for pages with recent dates and meaningful change ratios. Test `has_recent_date()` with various date formats. |
| G5.10 | Open | | | Run full test suite to verify noise filtering does not break existing pipeline tests. Confirm that benchmark and vendor pages are not incorrectly filtered. |

### Phase G5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G5: Noise filtering — support thread exclusion, low-value page detection, date validation`

---

## Phase G6: Discovery Automation

**Goal:** Implement a model slug discovery queue that triggers follow-up searches when new models are detected, and add path pattern probing for new vendor domains. After this phase, new model appearances automatically trigger multi-source corroboration searches, and new vendor path families are discovered dynamically.

**Depends on:** G2 (verification chain must be in place for follow-up claims to flow correctly), G3 (Semantic Scholar collector must exist for research follow-up searches), G4 (all source pages must be configured so follow-up searches have targets).

**Gaps addressed:** #9 (no automatic follow-up on new model discovery), #10 (no dynamic path pattern crawling).

| Task | Status | Started | Completed | Description |
|---|---|---|---|---|
| G6.1 | Open | | | Create `ai_benchmark/processing/discovery_queue.py` with `DiscoveryQueue` class. Maintains an in-memory set of known model slugs (loaded from DB on init). Exposes `check_new_slug(model_slug) -> bool` — returns True if slug has not been seen before and adds it to the set. |
| G6.2 | Open | | | Create `FollowUpTask` model in `ai_benchmark/models/discovery.py`. Fields: `id` (PK), `model_slug` (String 200), `organization` (String 200), `task_type` (String 50 — one of: "pricing_search", "release_notes_search", "system_card_search", "benchmark_coverage_search"), `status` (String 20, default "pending"), `created_at` (DateTime), `completed_at` (DateTime, nullable). |
| G6.3 | Open | | | Add `enqueue_follow_up(session, model_slug, organization)` async function in `ai_benchmark/processing/discovery_queue.py`. Creates 4 `FollowUpTask` records (one per task_type) for the new model slug. |
| G6.4 | Open | | | Integrate discovery queue into `process_item()` in `ai_benchmark/processing/pipeline.py`. After event creation, if `model_slug` is not None, call `discovery_queue.check_new_slug(model_slug)`. If True, call `enqueue_follow_up(session, model_slug, organization)` to create 4 follow-up task records. |
| G6.5 | Open | | | Create `execute_follow_up_tasks()` async function in `ai_benchmark/processing/discovery_queue.py`. Queries pending `FollowUpTask` records, and for each task type: constructs a targeted search — for "pricing_search", searches the org's pricing page URL; for "benchmark_coverage_search", queries benchmark leaderboards for the model slug. Marks tasks as completed or failed. |
| G6.6 | Open | | | Add schedule entry in `ai_benchmark/config/schedules.toml` for discovery follow-up: `organization = "Discovery"`, `cron = "*/30 * * * *"` (every 30 minutes), `max_concurrent = 1`. |
| G6.7 | Open | | | Create `ai_benchmark/processing/path_prober.py` with `PATH_FAMILIES` list: `["/news", "/blog", "/research", "/docs", "/changelog", "/release-notes", "/pricing", "/models", "/system-cards", "/leaderboard", "/papers"]`. Add `probe_domain(base_domain, fetcher) -> list[str]` that issues HEAD requests to each path family on the domain and returns paths that return 200. |
| G6.8 | Open | | | Create `discover_new_paths()` async function in `ai_benchmark/processing/path_prober.py`. Loads all unique `base_domain` values from the `sources` table, runs `probe_domain()` for each, compares discovered paths against configured `canonical_url` values in the `pages` table. Returns a list of `(domain, path)` tuples not yet configured. Logs discoveries at INFO level. |
| G6.9 | Open | | | Add schedule entry in `ai_benchmark/config/schedules.toml` for path probing: `organization = "PathProber"`, `cron = "0 3 * * 0"` (weekly, Sunday 3 AM), `max_concurrent = 1`. |
| G6.10 | Open | | | Create Alembic migration for `follow_up_tasks` table: new migration `006_discovery_automation.py`. |
| G6.11 | Open | | | Write tests in `tests/test_discovery_queue.py` — test `check_new_slug()` returns True for first occurrence and False for repeats, test `enqueue_follow_up()` creates 4 task records, test `execute_follow_up_tasks()` marks tasks as completed. Integration test: process an item with a new model slug, verify follow-up tasks are created. |
| G6.12 | Open | | | Write tests in `tests/test_path_prober.py` — test `probe_domain()` with mocked HTTP responses (some 200, some 404), test `discover_new_paths()` returns only unconfigured paths. |

### Phase G6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Gap Phase G6: Discovery automation — model slug follow-up queue, path pattern probing`

---

## Gap-to-Phase Traceability Matrix

| Gap # | Severity | Description | Phase |
|---|---|---|---|
| 1 | Critical | Semantic Scholar has no collector class | G3 |
| 2 | Critical | Research papers bypass triage pipeline | G3 |
| 3 | Critical | Pricing page snapshots not linked to claims | G1 |
| 4 | Critical | Benchmark variant data lost in pipeline | G1 |
| 5 | High | Confidence tier mapping incomplete | G2 |
| 6 | High | SWE-bench only monitors Verified | G4 |
| 7 | High | Model release verification chain not enforced | G2 |
| 8 | High | Cohere missing pricing and model docs pages | G4 |
| 9 | High | No automatic follow-up on new model discovery | G6 |
| 10 | High | No dynamic path pattern crawling | G6 |
| 11 | Medium | Claim records missing page_title | G2 |
| 12 | Medium | Google Gemini missing rate limits page | G4 |
| 13 | Medium | OpenAI missing system cards page | G4 |
| 14 | Medium | Artificial Analysis methodology extraction disabled | G4 |
| 15 | Medium | LMArena arena tabs not separately monitored | G4 |
| 16 | Medium | HLE missing Scale leaderboard hub | G4 |
| 17 | Medium | Cross-reference conflict relationships not used | G2 |
| 18 | Medium | Model slug not in dedup composite key | G1 |
| 19 | Medium | Reuters newsletter URL not configured | G4 |
| 20 | Medium | Community forum support thread filtering missing | G5 |
| 21 | Medium | Low-value page filtering not implemented | G5 |
| 22 | Medium | GitHub discovery missing xAI and Cohere orgs | G4 |
| 23 | Medium | No research enrichment retry mechanism | G3 |

---

## Phase Dependency Graph

```
G1 (Schema)
 ├──> G2 (Verification + Tiers)
 │     └──> G5 (Noise Filtering)
 │            └──> G6 (Discovery Automation)
 ├──> G3 (Research Triage) ──> G6
 └──> G4 (Source Catalog) ──> G6
```

All critical and high gaps are addressed in G1-G4. Medium gaps are distributed across G1-G5. Discovery automation (G6) depends on all prior phases being stable.
