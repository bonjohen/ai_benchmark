# Collection Pipeline Remediation — Implementation Plan

**Source document:** `docs/collection_remediation_design.md`

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
| Language | Python 3.12+ |
| Testing | pytest, pytest-asyncio |
| Linting | ruff (E/F/I/N/W/UP/B/SIM/TCH, line-length 100, py312) |
| HTML Parsing | BeautifulSoup + lxml |
| HTTP | httpx (async) |
| Database | SQLAlchemy 2.0 async (aiosqlite) |

---

## Phase 1: Quality Filter + Date Parsing

**Goal:** Research paper and forum sources pass through the quality filter. `extract_date()` handles ISO 8601 timestamps. arXiv and HF Forums items carry proper dates. Recovers ~112 papers + ~30 forum topics per run.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-30 09:10 AM | 2026-03-30 09:11 AM | Expand `dateless_page_types` in `ai_benchmark/processing/quality_filter.py:67` to add `"papers index"`, `"trending papers"`, `"recent submissions"`, `"forum index"`, `"discourse json"`, `"leaderboard docs"` |
| 1.2 | Completed | 2026-03-30 09:11 AM | 2026-03-30 09:11 AM | Add `candidate_paper` item-type exemption in `quality_filter.py:68` — if all items have `item_type == "candidate_paper"`, skip date check regardless of page type |
| 1.3 | Completed | 2026-03-30 09:12 AM | 2026-03-30 09:12 AM | Fix `extract_date()` in `ai_benchmark/processing/normalizer.py:510-531` — add ISO 8601 `T` separator pattern `(\d{4}-\d{2}-\d{2})T` before the existing `\b(\d{4}-\d{2}-\d{2})\b` regex |
| 1.4 | Completed | 2026-03-30 09:13 AM | 2026-03-30 09:13 AM | Set `date_text=date.today().isoformat()` on all `RawItem` objects in `ai_benchmark/sources/research/arxiv.py:70-78` for defense-in-depth |
| 1.5 | Completed | 2026-03-30 09:14 AM | 2026-03-30 09:14 AM | Add structured logging for JSON fetch failures in `ai_benchmark/sources/community/hf_forums.py:57-58` — log URL, status code, and error when `result.ok` is False |
| 1.6 | Completed | 2026-03-30 09:15 AM | 2026-03-30 09:17 AM | Update tests in `tests/test_quality_filter.py` — add cases for new page types in `dateless_page_types`, `candidate_paper` exemption, and verify existing trivial-change + short-title filters unchanged |
| 1.7 | Completed | 2026-03-30 09:17 AM | 2026-03-30 09:18 AM | Add `extract_date` tests in new `tests/test_normalizer.py` — verify ISO 8601 with T (`"2026-03-29T15:00:00.000Z"` → `"2026-03-29"`), plain ISO (`"2026-03-29"` → `"2026-03-29"`), existing formats preserved |
| 1.8 | Completed | 2026-03-30 09:19 AM | 2026-03-30 09:20 AM | Run `pytest` and `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — 916 passed, lint clean |
| 1.9 | Completed | 2026-03-30 09:20 AM | 2026-03-30 09:20 AM | Stage all Phase 1 changes |
| 1.10 | Completed | 2026-03-30 09:20 AM | 2026-03-30 09:20 AM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Expanded `dateless_page_types` with 6 new page types, added `candidate_paper` item-type exemption in quality_filter.py. Fixed `extract_date()` to handle ISO 8601 timestamps with T separator. Set `date_text` on arXiv RawItems. Added HF Forums JSON fetch failure logging. Added 11 quality filter tests and 12 normalizer tests.
- **Changes hosted at:** `ai_benchmark/processing/quality_filter.py`, `ai_benchmark/processing/normalizer.py`, `ai_benchmark/sources/research/arxiv.py`, `ai_benchmark/sources/community/hf_forums.py`, `tests/test_quality_filter.py`, `tests/test_normalizer.py`
- **Commit:** `Phase 1: Fix quality filter false positives and ISO 8601 date parsing`

---

## Phase 2: Collector Repairs

**Goal:** HF Leaderboard Docs extracts items from the documentation page. TechCrunch RSS handles malformed XML reliably. Recovers ~10-30 doc links + stabilizes ~20 news articles per run.
**Depends on:** Phase 1 (leaderboard docs page type added to `dateless_page_types`).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-30 09:22 AM | 2026-03-30 09:23 AM | Fetch `https://huggingface.co/docs/leaderboards/en/index` and inspect actual DOM structure to determine correct CSS selectors for the HF docs template |
| 2.2 | Completed | 2026-03-30 09:23 AM | 2026-03-30 09:25 AM | Rewrite `extract_items()` in `ai_benchmark/sources/community/hf_leaderboard_docs.py:24-56` — target links in main content area matching `/docs/leaderboards/` or `/spaces/` hrefs, with dedup via `seen_urls` set |
| 2.3 | Completed | 2026-03-30 09:25 AM | 2026-03-30 09:26 AM | Add BOM stripping to `_extract_rss()` in `ai_benchmark/sources/news/techcrunch.py:27-70` — `xml_text.lstrip("\ufeff").strip()` before parsing |
| 2.4 | Completed | 2026-03-30 09:26 AM | 2026-03-30 09:28 AM | Add regex-based last-resort RSS fallback in `techcrunch.py` — `_regex_extract_rss()` method using `re.findall(r"<item>(.*?)</item>", ...)` to extract title, link, pubDate when both parsers fail |
| 2.5 | Completed | 2026-03-30 09:28 AM | 2026-03-30 09:30 AM | Add/update tests in `tests/test_sources/test_community.py` for HF Leaderboard Docs — verify new selectors extract items from a representative HTML fixture |
| 2.6 | Completed | 2026-03-30 09:30 AM | 2026-03-30 09:32 AM | Add/update tests in `tests/test_sources/test_news.py` for TechCrunch — verify BOM-prefixed RSS, malformed RSS, and normal RSS all produce items |
| 2.7 | Completed | 2026-03-30 09:32 AM | 2026-03-30 09:33 AM | Run `pytest` and `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — fix any failures |
| 2.8 | Completed | 2026-03-30 09:34 AM | 2026-03-30 09:34 AM | Stage all Phase 2 changes |
| 2.9 | Started | 2026-03-30 09:34 AM | | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Rewrote HF Leaderboard Docs collector to target links in main content area with relevant href patterns, dedup, anchor/self-link filtering. Added BOM stripping and regex-based last-resort RSS fallback to TechCrunch collector. Added 6 new tests (realistic HF docs page, dedup, valid RSS, BOM RSS, regex fallback, empty RSS).
- **Changes hosted at:** `ai_benchmark/sources/community/hf_leaderboard_docs.py`, `ai_benchmark/sources/news/techcrunch.py`, `tests/test_sources/test_community.py`, `tests/test_sources/test_news.py`
- **Commit:** `Phase 2: Repair HF Leaderboard Docs collector and harden TechCrunch RSS parsing`

---

## Phase 3: External Access Hardening

**Goal:** Semantic Scholar collects papers with rate-limit resilience. OpenAI blocked pages are documented as expected. Recovers ~10-15 S2 papers per run without API key.
**Depends on:** Nothing (independent of Phases 1-2, but sequenced after for commit ordering).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-30 09:36 AM | 2026-03-30 09:37 AM | Add inter-query delay (`asyncio.sleep(3.0)`) between queries in `ai_benchmark/sources/research/semantic_scholar.py` `collect_via_api()` method (line 61-86) |
| 3.2 | Completed | 2026-03-30 09:37 AM | 2026-03-30 09:38 AM | Add per-query error handling in `collect_via_api()` — wrap each `search_paper()` call in try/except, log warning, continue to next query instead of failing entirely |
| 3.3 | Completed | 2026-03-30 09:38 AM | 2026-03-30 09:39 AM | Add missing API key warning in `collect_page()` override — log `semantic_scholar_no_api_key` with hint when `self.client.api_key` is None |
| 3.4 | Completed | 2026-03-30 09:39 AM | 2026-03-30 09:40 AM | Annotate OpenAI blocked pages in `ai_benchmark/config/sources.toml` (lines 17-44) with `notes` field documenting WAF block since 2026-03 and that RSS is the primary collection path |
| 3.5 | Completed | 2026-03-30 09:40 AM | 2026-03-30 09:41 AM | Annotate xAI blocked page (`x.ai/news`) and stale pages (`docs.x.ai/docs/release-notes`, `docs.x.ai/developers/models`) similarly in `sources.toml` |
| 3.6 | Completed | 2026-03-30 09:41 AM | 2026-03-30 09:43 AM | Update tests in `tests/test_sources/test_semantic_scholar.py` — verify inter-query delay, per-query error handling (mock one query failing, others succeed), and missing API key warning |
| 3.7 | Completed | 2026-03-30 09:43 AM | 2026-03-30 09:44 AM | Run `pytest` and `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — fix any failures |
| 3.8 | Completed | 2026-03-30 09:44 AM | 2026-03-30 09:44 AM | Stage all Phase 3 changes |
| 3.9 | Completed | 2026-03-30 09:44 AM | 2026-03-30 09:44 AM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Added 3-second inter-query delay and per-query try/except error handling in `collect_via_api()`. Added missing API key warning in `collect_page()`. Annotated OpenAI WAF-blocked pages (product-news, pricing, system-cards) and xAI blocked/stale pages (news, release-notes, models) with `notes` fields in sources.toml. Added 3 new tests for delay, error handling, and API key warning.
- **Changes hosted at:** `ai_benchmark/sources/research/semantic_scholar.py`, `ai_benchmark/config/sources.toml`, `tests/test_sources/test_semantic_scholar.py`
- **Commit:** `Phase 3: Harden Semantic Scholar rate limiting and document OpenAI/xAI access gaps`

---

## Phase 4: Pipeline Performance

**Goal:** LMArena processing drops from 6-10 minutes to under 3 minutes. No items lost. Batch dedup eliminates ~1,300 individual DB queries per LMArena run.
**Depends on:** Phase 1 (pipeline.py must be stable before refactoring).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-30 09:46 AM | 2026-03-30 09:47 AM | Implement `batch_find_duplicates(session, normalized_titles, organization)` in `ai_benchmark/processing/deduplicator.py` — single `SELECT ... WHERE normalized_title IN (...)` query returning dict of `{normalized_title: EventRecord}` |
| 4.2 | Completed | 2026-03-30 09:47 AM | 2026-03-30 09:49 AM | Refactor `process_items()` in `ai_benchmark/processing/pipeline.py:164-187` — pre-compute normalized titles, call `batch_find_duplicates()`, use result set for fast dedup lookups in the item loop |
| 4.3 | Completed | 2026-03-30 09:49 AM | 2026-03-30 09:50 AM | Add batch flush logic in `process_items()` — flush every 100 items instead of per-item, with a final flush after the loop |
| 4.4 | Completed | 2026-03-30 09:50 AM | 2026-03-30 09:51 AM | Add early return for same-source secondary benchmark entries in `ai_benchmark/processing/cross_reference.py` `build_cross_references()` — skip cross-ref queries when event_type is benchmark_result and classification is secondary |
| 4.5 | Completed | 2026-03-30 09:51 AM | 2026-03-30 09:53 AM | Update tests in `tests/test_deduplicator.py` — add test for `batch_find_duplicates()` with multiple titles, empty input, partial matches |
| 4.6 | Completed | 2026-03-30 09:53 AM | 2026-03-30 09:54 AM | Update tests in `tests/test_pipeline.py` — verify `process_items()` still creates events and claims correctly with batch dedup; verify dedup still works (duplicate items produce claims, not new events) |
| 4.7 | Completed | 2026-03-30 09:54 AM | 2026-03-30 09:55 AM | Update tests in `tests/test_cross_reference.py` — verify early return for secondary benchmark entries; verify non-benchmark events still get cross-references |
| 4.8 | Completed | 2026-03-30 09:55 AM | 2026-03-30 09:56 AM | Run `pytest` and `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — fix any failures |
| 4.9 | Completed | 2026-03-30 09:56 AM | 2026-03-30 09:56 AM | Stage all Phase 4 changes |
| 4.10 | Completed | 2026-03-30 09:56 AM | 2026-03-30 09:56 AM | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** Added `batch_find_duplicates()` for single SELECT IN batch dedup lookup. Refactored `process_items()` to pre-compute normalized titles, use batch dedup pre-check, and flush every 100 items. Added early return in `build_cross_references()` for secondary benchmark_result events. Added 6 new tests for batch dedup (multiple titles, empty input, partial matches), pipeline batch dedup correctness, and cross-ref skip/non-skip.
- **Changes hosted at:** `ai_benchmark/processing/deduplicator.py`, `ai_benchmark/processing/pipeline.py`, `ai_benchmark/processing/cross_reference.py`, `tests/test_deduplicator.py`, `tests/test_pipeline.py`, `tests/test_cross_reference.py`
- **Commit:** `Phase 4: Batch dedup and flush optimizations for LMArena processing performance`

---

## Phase 5: Cosmetic Cleanup

**Goal:** No `XMLParsedAsHTMLWarning` in collection logs. RSS XML content parsed with appropriate parser.
**Depends on:** Nothing (independent, sequenced last as lowest priority).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-03-30 09:58 AM | 2026-03-30 09:59 AM | Add XML content detection in `clean_html()` in `ai_benchmark/collection/differ.py:26-40` — check if content starts with `<?xml`, `<rss`, or `<feed`; use `"lxml-xml"` parser for XML, `"lxml"` for HTML |
| 5.2 | Completed | 2026-03-30 09:59 AM | 2026-03-30 10:00 AM | Update tests in `tests/test_differ.py` — add test cases for XML content (RSS feed) and HTML content, verify no warnings emitted for XML, verify HTML parsing unchanged |
| 5.3 | Completed | 2026-03-30 10:00 AM | 2026-03-30 10:01 AM | Run `pytest` and `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — fix any failures |
| 5.4 | Completed | 2026-03-30 10:01 AM | 2026-03-30 10:01 AM | Stage all Phase 5 changes |
| 5.5 | Completed | 2026-03-30 10:01 AM | 2026-03-30 10:01 AM | Commit all Phase 5 changes |

### Phase 5 Summary

- **Changes:** Added XML content detection in `clean_html()` — content starting with `<?xml`, `<rss`, or `<feed` is parsed with `lxml-xml` instead of `lxml` HTML parser, eliminating `XMLParsedAsHTMLWarning` from collection logs. Added 4 new tests for RSS, `<rss>` tag, HTML, and Atom feed content.
- **Changes hosted at:** `ai_benchmark/collection/differ.py`, `tests/test_differ.py`
- **Commit:** `Phase 5: Fix XMLParsedAsHTMLWarning by detecting XML content in differ`
