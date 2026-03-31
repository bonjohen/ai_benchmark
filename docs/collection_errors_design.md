# Collection Error Remediation — Design Document

## 1. Purpose

This document catalogs the recurring errors observed across 11 collection log files at `C:\ai-benchmark\logs\` and proposes solutions for each. The errors fall into 6 distinct categories, ranging from expected operational behavior (Cloudflare blocks) to critical failures (database locking).

## 2. Error Inventory

Aggregate counts across all collection logs:

| Error Type | Count | Severity | Category |
|---|---|---|---|
| `access_forbidden` (403) | 65 | Low | Cloudflare/WAF blocks |
| `low_value_page_filtered` | 49 | Info | Quality filter working as designed |
| `fetch_failed` / `fetch_error` | 58 | Medium | 403 retries that will never succeed |
| `collection_failed` (DB locked) | 22 | **Critical** | Concurrent DB access |
| `api_rate_limited` (429) | 22 | Medium | Semantic Scholar throttling |
| `page_error` (429) | 6 | Medium | Semantic Scholar throttling |
| `semantic_scholar_query_failed` | 1 | Low | Rate limit exhaustion |
| `semantic_scholar_no_api_key` | 1 | Info | Missing config |
| `rss_xml_parse_empty` | 1 | Low | Transient RSS feed issue |

## 3. Error Analysis

### 3.1 Cloudflare 403 Blocks — Retrying Permanently Blocked Pages

**65 `access_forbidden` + 58 `fetch_failed`/`fetch_error` across logs**

The same 5 OpenAI pages and 1 xAI page return 403 on every collection run. The coordinator retries these pages (attempt 0, 1, 2) despite the blocks being permanent Cloudflare WAF rejections, not transient failures.

**Blocked pages (same every run):**
- `platform.openai.com/docs/changelog`
- `platform.openai.com/docs/models`
- `openai.com/news/product-releases/`
- `openai.com/api/pricing/`
- `openai.com/index/system-cards/`
- `x.ai/news`

**Problem:** Each run wastes time retrying 6 pages x 3 attempts = 18 HTTP requests that will always fail. The retry logs create noise that obscures real errors. The Google News RSS fallback works for these sources, so the data loss is zero.

**Solution:** Mark pages as permanently blocked after N consecutive 403s. Skip them on subsequent runs until manually re-enabled. The `pages.consecutive_failures` column already exists but isn't consulted before fetching.

### 3.2 Database Locking — Concurrent SQLite Access

**22 `collection_failed` with `database is locked`**

All 22 occurred in a single log (`collect_20260329_214734.log`), affecting every source sequentially. This happens when two processes access the same SQLite database simultaneously — likely a collection run started while the eval server was also running, or two collection runs overlapped.

**Root cause:** SQLite has a single-writer lock. When the eval server holds a connection (e.g., serving a page request), a concurrent collection process that tries to write will get `OperationalError: database is locked` after the default 5-second timeout.

**Solutions:**
1. **Increase SQLite busy timeout** — set `connect_args={"timeout": 30}` on the async engine to wait longer for the lock.
2. **WAL mode** — enable Write-Ahead Logging (`PRAGMA journal_mode=WAL`) which allows concurrent reads during writes.
3. **Process guard** — the collect.bat script should check for an existing collection process before starting.
4. **Migrate to PostgreSQL** — eliminates the single-writer limitation entirely (long-term).

### 3.3 Semantic Scholar Rate Limiting

**22 `api_rate_limited` + 6 `page_error` + 1 `semantic_scholar_query_failed`**

Without an API key, the free tier allows ~1 request per 5 seconds. The collector sends 3 queries in rapid succession (with only 3-second delay between them), hitting the rate limit on the 2nd or 3rd query. The 30-second backoff (recently fixed) helps but doesn't eliminate the issue.

**Solutions:**
1. **Configure API key** — `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` in `.env` raises the limit significantly.
2. **Increase inter-query delay** — change the 3-second sleep between queries to 10 seconds for keyless operation.
3. **Reduce default query count** — send 1 query instead of 3 when no API key is configured.

### 3.4 Low-Value Page Filtering

**49 `low_value_page_filtered` across logs**

Pages filtered by the quality filter for stale dates or trivial content. This affects:
- Anthropic system cards page (stale dates)
- xAI release notes and models pages (stale dates)
- Terminal-Bench registry (stale dates)

**Assessment:** This is the quality filter working as designed. These pages contain outdated content that would produce low-value events. No fix needed.

### 3.5 Wasted Retries on Permanent Failures

The coordinator retries ALL fetch failures, including 403 Cloudflare blocks. The retry logic does not distinguish between:
- **Transient failures** (timeout, 500, 502, 503) — should retry
- **Permanent failures** (403 WAF, 404 not found) — should not retry

Each OpenAI 403 page generates 3 log entries (attempt 0, 1, 2) producing 15 warning lines per run for pages that will never succeed.

**Solution:** In the coordinator's fetch error handler, check the HTTP status code. Skip retries for 403 and 404. Only retry on 429, 500, 502, 503, 504, and timeout errors.

### 3.6 RSS Parse Empty

**1 `rss_xml_parse_empty`**

A single occurrence of an RSS feed returning empty XML. This is transient — the feed was likely temporarily unavailable. No fix needed.

## 4. Recommended Fixes

### Fix 1: Skip Permanently Blocked Pages (High — reduces 65+58 errors to 0)

Add a pre-fetch check in the coordinator: if `page.consecutive_failures >= 5` and the last error was a 403, skip the page and log `page_skipped_blocked` at info level instead of attempting the fetch.

**Files:** `coordination/coordinator.py`
**Effort:** Small

### Fix 2: Don't Retry 403/404 Errors (High — eliminates retry noise)

In the coordinator's retry logic, check the HTTP status code from the fetch error. Return immediately (no retry) for 403 and 404 responses.

**Files:** `coordination/coordinator.py`
**Effort:** Small

### Fix 3: Enable SQLite WAL Mode (Critical — fixes DB locking)

Add `PRAGMA journal_mode=WAL` to the engine connection event. WAL mode allows the eval server to read while the collector writes, eliminating the `database is locked` errors.

```python
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()
```

**Files:** `models/base.py` (create_engine function)
**Effort:** Small

### Fix 4: Increase Semantic Scholar Inter-Query Delay (Medium)

When no API key is configured, increase the sleep between queries from 3 seconds to 10 seconds. Also reduce default queries from 3 to 1 for keyless operation.

**Files:** `sources/research/semantic_scholar.py`
**Effort:** Small

### Fix 5: Suppress Info-Level Noise (Low)

Change `low_value_page_filtered` from `warning` to `debug` level since it's expected behavior. Change `access_forbidden` for known-blocked pages to `debug` after first occurrence.

**Files:** `collection/fetcher.py`, `processing/quality_filter.py`
**Effort:** Small

## 5. Priority Order

| # | Fix | Impact | Errors Eliminated |
|---|---|---|---|
| 3 | SQLite WAL mode | Critical | 22 DB locked errors |
| 1 | Skip blocked pages | High | 65 access_forbidden |
| 2 | Don't retry 403/404 | High | 58 fetch_failed retries |
| 4 | S2 inter-query delay | Medium | 22 rate_limited |
| 5 | Suppress info noise | Low | 49 low_value warnings |

After all fixes, a clean collection run should produce **0 warnings** for the known-blocked pages and rate-limited APIs, with only genuine unexpected errors surfaced.

## 6. Acceptance Criteria

1. After Fix 3: Two processes (server + collector) can run simultaneously without `database is locked`.
2. After Fixes 1+2: Collection log for a full run contains 0 lines mentioning `access_forbidden` or `fetch_error` for the 6 known-blocked URLs.
3. After Fix 4: Semantic Scholar queries complete without 429 errors when no API key is set.
4. After Fix 5: `low_value_page_filtered` no longer appears at warning level in logs.
5. A clean collection run log should be <50 lines (currently >200 due to retry noise).
