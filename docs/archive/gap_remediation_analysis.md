# Core Requirements Gap Analysis

Audit of the codebase against `docs/core_requirements.md` Sections 1-5. Conducted 2026-03-28.

---

## Critical Issues

### 1. Semantic Scholar Has No Collector Class

**Requirement (Section 1, Source #18):** Semantic Scholar is one of the 22 required sources with API-based collection.

**Status:** `sources/research/semantic_scholar.py` contains only `SemanticScholarClient` (an API client), not a `SourceCollector` subclass. It is not registered in `COLLECTOR_CLASSES` in `sources/registry.py` and cannot be instantiated via `get_collector()`.

**Impact:** Semantic Scholar cannot participate in scheduled collection. The enrichment client exists but is disconnected from the pipeline.

### 2. Research Papers Bypass Triage Pipeline

**Requirement (Section 5, line 232):** "arXiv and Hugging Face Papers should feed a 'candidate papers' queue, not your authoritative knowledge base."

**Status:** `ArxivCollector` and `HFPapersCollector` return `RawItem` objects that flow through `pipeline.process_item()` directly into `EventRecord` storage. The triage pipeline in `processing/triage.py` (ingest_candidate -> enrich_candidate -> promote) exists but is never called from the main processing pipeline. Research items are treated identically to official vendor announcements.

**Impact:** Low-signal preprints are stored as authoritative events. The triage gate (candidate -> enriched -> promoted) is dead code in practice. HF Papers collector has no relevance filtering at all.

### 3. Pricing Page Snapshots Not Linked to Claims

**Requirement (Section 3, line 196):** "Store both the detected HTML snapshot and the timestamp of observation, because price pages often change without a corresponding blog post."

**Status:** The `Snapshot` model exists in `models/sources.py` and the snapshot manager works, but pricing-change claims in `ClaimRecord` have no `snapshot_id` foreign key. The pipeline does not invoke snapshot storage specifically for pricing events. There is no audit trail linking a price change claim to the HTML state that triggered it.

**Impact:** Pricing changes cannot be audited or reconstructed after the fact.

### 4. Benchmark Variant Data Lost in Pipeline

**Requirement (Section 3, line 194):** "Record variant (e.g., SWE-bench Verified vs Lite vs Pro) and evaluation conditions."

**Status:** `SWEBenchCollector` extracts variant and conditions into `RawItem.metadata`, but `EventRecord` has no `benchmark_variant` or `evaluation_conditions` fields. This metadata is lost when items are normalized into events.

**Impact:** Cannot distinguish SWE-bench Verified claims from Lite/Pro. Cannot track contamination risk by variant. Cannot query "show me only Verified results."

---

## High-Severity Issues

### 5. Confidence Tier Mapping Incomplete

**Requirement (Section 3/5):** Five confidence tiers: `official_self_report`, `benchmark_owner_report`, `high_secondary` (Reuters), `medium_discovery` (TechCrunch), `low_discovery` (forums/GitHub).

**Status:** `normalizer.py` maps only 3 base tiers by classification:
```
primary -> official_self_report
secondary -> high_secondary
discovery-only -> low_discovery
```
Missing: `benchmark_owner_report` (all benchmarks get `high_secondary`, same as Reuters) and `medium_discovery` (TechCrunch gets `high_secondary`, same as Reuters).

**Impact:** Reuters and TechCrunch are weighted equally. Benchmark-owner reports are indistinguishable from independent analysis. The verification hierarchy cannot differentiate source authority within the "secondary" classification.

### 6. SWE-bench Only Monitors Verified Variant

**Requirement (Section 1, Source #11):** Monitor Verified, Lite, Full, Multilingual, and Multimodal leaderboards.

**Status:** `sources.toml` configures only `https://www.swebench.com/verified.html`. The collector code recognizes all variants via `SWEBENCH_VARIANTS` and has `_detect_variant()`, but the other 4 pages are not configured for polling.

**Impact:** Lite, Full, Multilingual, and Multimodal leaderboard changes go undetected.

### 7. Model Release Verification Chain Not Enforced

**Requirement (Section 3, line 192):** "vendor launch surface > developer docs/model catalog > pricing > changelog/release notes > system card. Confirmed when at least two official surfaces align."

**Status:** `verification.py` defines the chain stages but `check_confirmation()` only counts claims with `official_self_report` tier. It does not enforce ordering or require specific source types in sequence. A system card claim counts the same as a launch page claim.

**Impact:** Verification is quantity-based (2+ claims), not ordering-aware. The chain hierarchy is decorative.

### 8. Cohere Missing Pricing and Model Docs Pages

**Requirement (Section 1, Source #6):** Monitor release notes, blog, pricing, and model docs.

**Status:** `sources.toml` configures only release notes and blog for Cohere. No pricing page (e.g., `docs.cohere.com/pricing`) and no model documentation page (e.g., `docs.cohere.com/docs/command-a`) are configured.

**Impact:** Cohere pricing changes and new model documentation go undetected.

### 9. No Automatic Follow-Up When New Models Are Discovered

**Requirement (Section 4, paragraph 1):** "Whenever a new model slug appears, immediately queue follow-up searches for pricing, release notes, system card/model card, and benchmark coverage."

**Status:** `normalizer.py` has `extract_model_slug()` which identifies model slugs from text, but there is no mechanism to trigger follow-up searches. No discovery queue, no targeted re-fetch, no cross-source search triggered by new slug detection.

**Impact:** New models are catalogued but their pricing, system cards, and benchmark coverage may not be discovered with sufficient velocity.

### 10. No Dynamic Path Pattern Crawling

**Requirement (Section 4, paragraph 3):** "Crawl for path patterns rather than only watching homepages. The most productive path families in this domain are /news, /blog, /research, /docs, /changelog, /release-notes, /pricing, /models, /system-cards, /leaderboard, and /papers."

**Status:** All monitored paths are hardcoded in `sources.toml`. There is no mechanism to probe new vendor domains for standard path patterns or detect when vendors add new paths.

**Impact:** If a vendor launches a new page type (e.g., Cohere adds `/leaderboard`), it will not be discovered until manually configured.

---

## Medium-Severity Issues

### 11. Claim Records Missing page_title

**Requirement (Section 3, line 202):** Store "claim_text, source_type, source_name, page_title, observed_at, and a confidence tier."

**Status:** `ClaimRecord` has a `page_title` field but it is optional and `pipeline.process_item()` never populates it. The page title from collection is not propagated through `RawItem` to the claim creation step.

**Impact:** Cannot trace a claim back to the exact page that produced it.

### 12. Google Gemini Missing Rate Limits Page

**Requirement (Section 1, Source #3):** Monitor release notes, pricing, rate limits, models catalog, and DeepMind blog.

**Status:** `sources.toml` configures 4 of 5 required pages. The rate limits page (`ai.google.dev/gemini-api/docs/rate-limits`) is not configured.

**Impact:** Rate limit changes go undetected.

### 13. OpenAI Missing System Cards Page

**Requirement (Section 1, Source #1):** Monitor product newsroom, API changelog, pricing, models, and system cards.

**Status:** `sources.toml` configures 4 pages. No system cards page is configured. The collector docstring mentions system cards but no extractor is implemented.

**Impact:** OpenAI system card publications go undetected.

### 14. Artificial Analysis Methodology Extraction Disabled

**Requirement (Section 1, Source #8):** Monitor performance leaderboard and methodology.

**Status:** The methodology page is configured in `sources.toml`, but `artificial_analysis.py` line 18 returns an empty list for methodology pages: `if "methodology" in page.page_type: return []`.

**Impact:** Methodology changes are polled but never extracted.

### 15. LMArena Arena Tabs Not Separately Monitored

**Requirement (Section 1, Source #9):** Monitor overview leaderboard and dedicated arena tabs (expert, hard prompts, coding, math, longer query).

**Status:** Only `https://lmarena.ai/leaderboard/` is configured. Arena sub-tabs are not separately polled.

**Impact:** Category-specific ranking shifts (e.g., coding-only leaderboard changes) are not tracked independently.

### 16. HLE Missing Scale Leaderboard Hub

**Requirement (Section 1, Source #13):** Monitor both the general Scale leaderboard page and the HLE-specific page.

**Status:** Only the HLE page (`scale.com/leaderboard/humanitys_last_exam`) is configured. The general Scale leaderboard hub (`scale.com/leaderboard`) is not monitored.

**Impact:** New benchmark families added to Scale's hub go undetected.

### 17. Cross-Reference Conflict Relationships Not Used

**Requirement (Section 3):** Conflicting claims should be identified and linked.

**Status:** `CrossReference` model supports `conflicts_with` and `cites` relationship types, but `cross_reference.py` only creates `confirms` and `supplements` relationships. Conflict detection in `verification.py` uses `SequenceMatcher.ratio() < 0.5` which flags wording differences as conflicts, not semantic disagreements.

**Impact:** True conflicts (e.g., vendor claims $0.05, benchmark owner reports $0.03) are not linked. Wording differences create false-positive conflicts.

### 18. Model Slug Not in Deduplication Composite Key

**Requirement (Section 5, line 238):** "For official model events, also store {model_slug, version_date} when available."

**Status:** `find_model_duplicate()` exists in `deduplicator.py` and searches by model_slug, but model_slug is not part of the `EventRecord` unique constraint. The same model release from different official surfaces (newsroom vs changelog) creates multiple events instead of one event with multiple claims.

**Impact:** Multi-surface confirmation creates duplicate events rather than reinforcing a single event with multiple claims.

### 19. Reuters Newsletter URL Not Configured

**Requirement (Section 2, Page #19):** Monitor both Reuters AI category and the Artificial Intelligencer newsletter.

**Status:** Only `reuters.com/technology/artificial-intelligence/` is configured. The newsletter URL is not explicitly monitored.

**Impact:** Newsletter-specific content may be missed if not also published to the AI category page.

### 20. Community Forum Support Thread Filtering Missing

**Requirement (Section 5, line 236):** "Ignore generic support threads, repeated 'how do I run this model?' posts, and repo noise."

**Status:** `hf_forums.py` extracts all topics matching CSS selectors with no filtering for support threads, help questions, or debug requests.

**Impact:** Noise from support threads enters the pipeline and relies entirely on downstream deduplication.

### 21. Low-Value Page Filtering Not Implemented

**Requirement (Section 5, line 240):** "Skip marketing landing pages without dates, duplicate localized docs pages, stale archived leaderboard pages, broken Spaces, and generic overview pages."

**Status:** No date validation during extraction. No language-aware deduplication. No archival/deprecation detection. No change-ratio threshold for stable pages.

**Impact:** Bandwidth spent polling pages that rarely produce actionable events.

### 22. GitHub Discovery Missing xAI and Cohere Orgs in Config

**Requirement (Section 1, Source #21):** Monitor official orgs including all major vendors.

**Status:** `sources.toml` configures GitHub orgs for OpenAI, Anthropic, Google, and Mistral. xAI (`xai-org`) and Cohere (`cohere-ai`) are referenced in `WATCHED_ORGS` in code but not in the config file.

**Impact:** xAI and Cohere GitHub activity not polled unless the code-level constant overrides config.

### 23. No Research Enrichment Retry Mechanism

**Requirement (Section 4):** Enrich candidate papers via Semantic Scholar.

**Status:** `triage.py` enrichment can fail due to API errors, leaving papers in "pending" status. There is no scheduled retry job in `schedules.toml` for re-enrichment of failed candidates.

**Impact:** Papers that fail enrichment on first attempt are permanently stuck as pending.

---

## Compliant Areas

The following requirements are well-implemented:

- **Polling cadences:** All Section 5 cadence requirements are met with proper offset scheduling to avoid thundering herd.
- **Circuit breaker:** `SourceHealthTracker` trips after 5 consecutive failures per source.
- **Composite dedup key:** `{normalized_title, org, source_type, canonical_path, published_date}` implemented as DB constraint.
- **Fuzzy dedup:** 0.85 SequenceMatcher threshold as specified.
- **Separate claim records:** Claims from different sources are never merged.
- **Full processing chain:** normalize -> deduplicate -> create event -> create claim -> update confirmation -> cross-reference.
- **Community minimal metadata:** HF Forums and GitHub discovery extract only title, author, timestamp, tags, and outbound links.
- **News tier ordering:** Reuters polled every 3h, TechCrunch every 6h, community daily.
- **arXiv category coverage:** cs.AI, cs.CL, cs.LG all monitored every 12h.
- **HF Papers:** Both papers home and trending pages monitored daily.
- **21 of 22 collector classes** properly registered and functional.
- **Complete vendor coverage:** Anthropic (5/5 pages), xAI (3/3), Mistral (3/3), Meta (2/2), LiveBench (2/2), Terminal-Bench (2/2), arXiv (3/3), HF Papers (2/2), TechCrunch (1/1), HF Forums (1/1).

---

## Summary Counts

| Severity | Count |
|---|---|
| Critical | 4 |
| High | 6 |
| Medium | 13 |
| **Total gaps** | **23** |
