# Data Pipeline Failures — Design Document

## 1. Purpose

This document catalogs the data quality failures observed after the first production collection run (2026-03-30) and proposes fixes for each. The database contains 2,933 events, 20,113 claims, 245 candidate papers, and 333,298 cross-references. Despite a successful collection (exit code 0), several systemic issues reduce the usefulness of the collected data.

## 2. Failure Inventory

### 2.1 Missing Model Slugs (2,402 events — 82% of all events)

**Severity: High**

2,402 of 2,933 events have `model_slug = NULL`. Only 531 events have a model slug. The NULL-slug events include high-value items that clearly reference specific models but the normalizer failed to extract the slug.

Examples of model releases with no slug:
- "We've launchedClaude Sonnet 4.6, our latest balanced model..." (Anthropic)
- "We've launchedClaude Opus 4.5, our most intelligent model..." (Anthropic)
- "FeatureClaude Opus 4.6Claude Sonnet 4.6Claude Haiku 4.5" (Anthropic API update)

These titles contain model names but the normalizer's `extract_model_slug()` did not match them. The HTML extraction also strips whitespace between inline elements, producing concatenated text like "launchedClaude" and "FeatureClaude" which breaks pattern matching.

**Breakdown by org and event type (top entries):**

| Organization | Event Type | NULL Slug Count |
|---|---|---|
| LMArena | announcement | 271 |
| Reuters | announcement | 245 |
| Anthropic | announcement | 182 |
| Mistral AI | announcement | 182 |
| Cohere | announcement | 163 |
| Google | announcement | 140 |
| Anthropic | model_release | 67 |
| Anthropic | api_update | 53 |
| Mistral AI | model_release | 43 |
| Anthropic | pricing_change | 29 |

**Root causes:**
1. HTML text extraction concatenates adjacent inline elements without spaces (e.g., `<strong>Claude Opus 4.6</strong>` inside a sentence becomes "launchedClaude Opus 4.6").
2. The slug extractor regex does not match model names embedded in longer phrases.
3. News/announcement events from Reuters, TechCrunch, and Google News RSS describe multiple models per title but the extractor picks none.
4. SWE-bench multilingual entries use repository names as titles (e.g., "SWE-bench: redis/redis = C") which have no model name.
5. Pricing and API update events reference models in tabular or list formats that the extractor cannot parse.

### 2.2 LMArena Events Mistyped as "announcement" (778 events)

**Severity: Medium**

778 LMArena events have `event_type = "announcement"` and `benchmark_variant IS NOT NULL`. These are benchmark leaderboard entries that should be typed as `"benchmark_result"`. The LMArena collector assigns `item_type = "unknown"` or lets the normalizer default to `"announcement"`, even though the data contains benchmark variant and rank information.

**Impact:** These events are excluded from benchmark-specific queries that filter on `event_type = "benchmark_result"`. The benchmarks page shows leaderboard data only because it queries on `benchmark_variant IS NOT NULL`, which happens to work. But any logic that checks event_type will miss them.

### 2.3 LMArena Rank-Only Data — Missing Elo Scores (681 events)

**Severity: Medium**

All 681 LMArena events store `raw_content = "Rank: N, Variant: arena_elo_*, Conditions: None"` — a rank position (1, 2, 3...) instead of the actual Elo score (1447, 1318, etc.). The Elo scores exist in the LMArena HTML but the collector only extracts the ordinal rank column.

The claim records DO contain Elo scores in the claim_text field (e.g., "LMArena: gemini-3-pro = 1447"). This means the Elo values are available during claim creation but lost in the event raw_content.

**Impact:** The benchmark leaderboard cannot show actual Elo scores. The score extraction function (`extract_benchmark_score`) tries to parse numbers from raw_content and incorrectly returns rank numbers as if they were scores, inverting the leaderboard order (rank 197 scores higher than rank 1).

### 2.4 Title Truncation at 200 Characters (49 events)

**Severity: Low (fixed)**

49 events had titles truncated at exactly 200 characters — 47 from Anthropic, 2 from Google. The `extract_title()` function found a sentence boundary at ~200 chars in long changelog paragraphs. The function's default `max_length` was 500 but sentence-breaking could occur much earlier.

**Status:** Fixed in commit `65a9857`. Default raised to 2000. Future collections will store full titles. Existing truncated titles require a re-collection to correct.

### 2.5 Research Pipeline Stalled — 0 Enriched Papers (245 candidates stuck)

**Severity: Medium**

245 candidate papers were discovered (all `status = "pending"`) but none were enriched or promoted. The enrichment step requires Semantic Scholar API calls, which are rate-limited at the free tier. The collector was throttled (429 errors) after ~10 queries, and the remaining candidates were never processed.

**Root causes:**
1. No `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` configured — free tier has very low rate limits.
2. The retry backoff was 5 seconds (now fixed to 30 seconds), causing rapid retry exhaustion.
3. No retry mechanism for pending candidates on subsequent collection runs.

### 2.6 Source and Page Tables Empty (0 rows)

**Severity: Low**

The `sources` and `pages` tables have 0 rows despite successful collection. The collection coordinator creates sources and pages dynamically during collection but the current coordinator implementation uses the source catalog in memory without persisting to these tables. The `status` CLI command queries these tables and shows 0 events per source.

**Impact:** The `ai-benchmark status` command shows all zeros. Per-source health tracking based on the `pages` table (consecutive_failures, last_polled_at) does not function.

### 2.7 Cross-Reference Explosion (333,298 records — 99.98% supplements)

**Severity: Low**

333,298 cross-references were created, of which 333,237 (99.98%) are type `"supplements"` and only 61 are `"confirms"`. The cross-reference builder's org + event type strategy matches too broadly: any two events from the same org with the same event type within 3 days creates a `"supplements"` link. With 2,933 events mostly typed as `"announcement"`, this produces a combinatorial explosion.

**Impact:** Cross-reference counts per event are inflated and meaningless. The "supplements" relationship adds no useful signal at this volume.

### 2.8 Cloudflare/WAF Blocks (403 errors on 6 pages)

**Severity: Low (by design)**

5 OpenAI pages and 1 xAI page return HTTP 403 (Cloudflare protection). The pipeline falls back to Google News RSS feeds for these sources, which successfully collected 100 items per source. This is working as designed.

**Blocked pages:** `openai.com/news/product-releases/`, `platform.openai.com/docs/changelog`, `platform.openai.com/docs/models`, `openai.com/api/pricing/`, `openai.com/index/system-cards/`, `x.ai/news`

### 2.9 Unknown Model Publishers (160 model entities)

**Severity: Low (partially fixed)**

160 of 495 model entities have `publisher = "Unknown"`. The slug-based publisher inference handles major vendors (Anthropic, OpenAI, Google, Meta, etc.) but cannot identify smaller or less-common model publishers from slug patterns alone.

**Examples:** `tulu-3-70b`, `athene-v2-chat`, `eureka-chatbot`, `koala-13b`, `solar-pro-preview`

## 3. Recommended Fixes

### 3.1 Model Slug Extraction — Normalizer Enhancement

**Priority: High. Fixes §2.1.**

The `extract_model_slug()` function in `processing/normalizer.py` needs:

1. **Whitespace normalization before extraction** — insert spaces between CamelCase boundaries and before/after HTML-concatenated words (e.g., "launchedClaude" → "launched Claude").
2. **Expanded model name dictionary** — a lookup table of known model names and their canonical slugs: `{"Claude Opus 4.6": "claude-opus-4.6", "GPT-5": "gpt-5", "Gemini 3 Pro": "gemini-3-pro", ...}`. Run extraction against this dictionary first, fall back to regex patterns.
3. **Multi-model title handling** — titles mentioning multiple models (e.g., "Claude Opus 4.6, Sonnet 4.6, Haiku 4.5") should extract the primary model or create multiple events.
4. **Post-collection backfill** — a CLI command `ai-benchmark analyze backfill-slugs` that scans existing NULL-slug events and applies the improved extractor retroactively.

### 3.2 LMArena Event Type Classification

**Priority: Medium. Fixes §2.2.**

The LMArena collector should set `item_type = "benchmark_result"` (not `"unknown"`) for items that have a benchmark variant and rank data. Alternatively, the normalizer's `classify_event_type()` should check for the presence of `benchmark_variant` metadata and override the type to `"benchmark_result"`.

A backfill command should update the 778 existing mistyped events:
```sql
UPDATE event_records SET event_type = 'benchmark_result'
WHERE organization = 'LMArena' AND benchmark_variant IS NOT NULL AND event_type = 'announcement';
```

### 3.3 LMArena Elo Score Extraction

**Priority: Medium. Fixes §2.3.**

Two approaches:

**Option A (collector fix):** Modify the LMArena collector to extract the Elo score column from the leaderboard HTML alongside the rank. Store it in `raw_content` as `"Rank: N, Elo: NNNN, Variant: ..."`.

**Option B (claim-based extraction):** The Elo scores already exist in claim_text (`"LMArena: model = 1447"`). Add a post-processing step that copies the score from the claim into the event's raw_content or a dedicated score field, and use this value for leaderboard display.

Option B is lower-effort since the data already exists.

### 3.4 Research Enrichment Pipeline

**Priority: Medium. Fixes §2.5.**

1. Configure `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` in production `.env`.
2. Add a retry mechanism to the enrichment step: on each collection run, process pending candidates that haven't been retried recently (respect `retry_count` and `last_retry_at` columns that already exist).
3. The 30-second backoff (already fixed) will reduce 429 failures.

### 3.5 Source/Page Table Population

**Priority: Low. Fixes §2.6.**

The collection coordinator should persist source and page records to the database on first collection. This enables the `status` command, per-page health tracking, and snapshot association. The source catalog TOML already has all needed data — the coordinator just needs to upsert it into the DB.

### 3.6 Cross-Reference Threshold Tightening

**Priority: Low. Fixes §2.7.**

The `"supplements"` strategy in `processing/cross_reference.py` should be tightened:
1. Require a model_slug match (not just org + event_type + time window).
2. Reduce the time window from 3 days to 1 day for supplements.
3. Add a maximum cap on supplements per event (e.g., 10).
4. Consider removing the supplements strategy entirely and relying only on model slug + time window and arXiv ID strategies.

### 3.7 Re-collection for Corrected Titles

**Priority: Low. Fixes remaining §2.4.**

After deploying the `extract_title()` fix, run a targeted re-collection for Anthropic and Google sources to replace the 49 truncated titles:
```
ai-benchmark collect --source Anthropic
ai-benchmark collect --source Google
```

## 4. Implementation Priority

| # | Fix | Severity | Effort | Events Affected |
|---|---|---|---|---|
| 3.1 | Model slug extraction | High | Large | 2,402 |
| 3.2 | LMArena event type | Medium | Small | 778 |
| 3.3 | Elo score extraction | Medium | Medium | 681 |
| 3.4 | Research enrichment | Medium | Small (config) | 245 |
| 3.5 | Source/page population | Low | Medium | 0 (infra) |
| 3.6 | Cross-ref tightening | Low | Small | 333,237 |
| 3.7 | Title re-collection | Low | Trivial | 49 |

## 5. Acceptance Criteria

1. After §3.1: >80% of events should have a non-NULL model_slug (currently 18%).
2. After §3.2: 0 events with `event_type = "announcement" AND benchmark_variant IS NOT NULL`.
3. After §3.3: Benchmark leaderboards show actual Elo scores, not rank numbers.
4. After §3.4: Candidate papers progress from `pending` to `enriched` status.
5. After §3.5: `ai-benchmark status` shows non-zero event counts per source.
6. After §3.6: Cross-reference count drops from 333K to a meaningful number (<5K).
