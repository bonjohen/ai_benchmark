# Plan: Fix Collection Issues from Backfill Run

**Status**: Completed (2026-03-29)

## Context

The first `collect --since 2026-01-01` backfill run (2026-03-29) produced 3,401 events but surfaced 6 categories of issue: 403 Cloudflare blocks, 404 stale URLs, 429 rate limiting, stale-date false positives, zero-item parsers, and over-aggressive filtering. This plan addresses each root cause with targeted fixes.

## Fix 1: Skip quality filter in backfill mode

**Root cause**: `_collect_page_inner()` computes dynamic `max_age_days` when `since_date` is set, but still calls `is_low_value_page()`. Pages that aren't cold-start (change_ratio < 1.0) and have items with unparseable dates get stale-filtered even in backfill mode. Affected: arXiv cs.CL, cs.LG, HF Papers (both pages).

**Fix**: In `base.py:_collect_page_inner()` (line ~175), skip the `is_low_value_page()` call entirely when `since_date` is set. The user explicitly requested backfill — quality filtering is counterproductive.

**File**: `ai_benchmark/sources/base.py`

## Fix 2: Add 429 retry to APIClient

**Root cause**: `APIClient.get()` (api_client.py:49) calls `response.raise_for_status()` which throws on 429 instead of retrying. The `Fetcher` has 429 handling with `Retry-After` support (fetcher.py:113-122), but `APIClient` lacks this entirely. Affected: Semantic Scholar (429 on first request → entire collection fails).

**Fix**: Add a retry loop to `APIClient.get()` that mirrors the Fetcher pattern: check for 429 status, extract `Retry-After` header (default 5s), sleep, retry up to 3 times. Import `asyncio` and add `logger` from structlog.

**File**: `ai_benchmark/collection/api_client.py`

## Fix 3: Remove 404 URLs from config

**Root cause**: Three URLs return 404 because the pages no longer exist on the live sites.

**Changes**:
- `sources.toml`: Remove SWE-bench `full.html` (lines 404-407) and `pro.html` (lines 409-413) page entries. Remove AA methodology page (lines 300-303).
- `graph_secondary.toml`: Remove `swebench.full` and `swebench.pro` nodes and all their edges. Remove `aa.methodology` node and its edges.
- `graph_primary.toml`: No changes (SWE-bench full/pro are in secondary graph only).
- Update `[graph]` metadata counts (`page_count`, `source_count`) to match.

**Files**: `ai_benchmark/config/sources.toml`, `ai_benchmark/config/graph_secondary.toml`

## Fix 4: Add Referer header to fetcher

**Root cause**: The fetcher sends browser-like headers but lacks a `Referer` header. Some Cloudflare WAF configurations flag requests without a referrer as bot traffic. Affected: OpenAI (5 pages), xAI (x.ai/news).

**Fix**: Add `"Referer": "https://www.google.com/"` and `"DNT": "1"` to `_DEFAULT_HEADERS` in fetcher.py (line ~36). This is a low-risk change that may help with some Cloudflare-protected sites. Full Cloudflare bypass would require a headless browser (out of scope).

**File**: `ai_benchmark/collection/fetcher.py`

## Fix 5: Relax HF Forums support thread filter

**Root cause**: Six regex patterns in `SUPPORT_THREAD_PATTERNS` (hf_forums.py:22-29) filter out nearly all forum topics. Patterns like `\berror\b` and `\bhow (do|can|to)\b` are too broad — they match legitimate discussion ("error analysis", "How do transformers handle long context?"). Result: 0 items from both HTML and JSON API paths.

**Fix**: Remove overly broad patterns (`\berror\b`, `\bbug\b`, `\bhow (do|can|to)\b`). Keep only clearly support-oriented patterns that combine help-seeking language with technical action words (`help.*install/setup/configure`, `not working`, `can't.*run/install/load`). Reduce from 6 patterns to 3.

**File**: `ai_benchmark/sources/community/hf_forums.py`

## Fix 6: TechCrunch RSS parser fallback

**Root cause**: `_extract_rss()` (techcrunch.py:24-60) uses `BeautifulSoup(xml_text, "lxml-xml")` to parse the WordPress RSS feed. If the feed returns unexpected content (HTML error page, redirect, changed format), the XML parser silently returns 0 items. Both pages returned `count=0` on the backfill run.

**Fix**: Add a fallback in `_extract_rss()`: if `lxml-xml` parsing yields 0 items, retry with `"lxml"` parser (handles XML-like HTML). Log a warning when the fallback triggers so we can diagnose feed issues.

**File**: `ai_benchmark/sources/news/techcrunch.py`

## Out of Scope

- **Full Cloudflare bypass** (headless browser) — would require Playwright/Selenium dependency; RSS fallback covers the gap for now
- **Mistral/Cohere HTML parsers returning 0** — these sites use JS rendering; RSS fallback is already working (Mistral: 40 events, Cohere: 15 events). HTML parser fixes would require live DOM inspection.
- **Semantic Scholar date filtering** — Could pass `publicationDateOrYear` to the API for backfill; deferred to a future enhancement

## Verification

1. `pytest` — all 666 tests pass
2. `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — clean
3. Manual spot-check: `ai-benchmark collect --since 2026-01-01 --source "arXiv / Cornell"` — cs.CL and cs.LG should no longer be stale-filtered
4. Check that `sources.toml` no longer references SWE-bench full/pro or AA methodology
5. Verify graph_secondary.toml node/edge counts match the `[graph]` metadata
