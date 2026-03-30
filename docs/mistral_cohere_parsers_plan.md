# Mistral/Cohere HTML Parser Fixes — Implementation Plan

**Source document:** `docs/mistral_cohere_parsers_pdr.md`

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
|---------|--------|
| RSC payload extraction | `re` (stdlib) — regex against `self.__next_f.push()` calls |
| HTML fragment re-parsing | `BeautifulSoup` with `lxml` (already installed) |
| Test fixtures | Saved HTML snapshots from live Mistral pages |

## Phase 1: RSC Payload Extraction Utility

**Goal:** A tested `extract_nextjs_rsc_payloads()` function exists in `base.py`, extracting string payloads from Next.js RSC streaming HTML.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1  | Completed | 2026-03-30 05:05 PM | 2026-03-30 05:07 PM | Add `extract_nextjs_rsc_payloads(html) -> list[str]` to `ai_benchmark/sources/base.py` alongside `extract_title()`. Regex finds `self.__next_f.push([...])` calls, extracts string payloads, handles escaped chars. |
| 1.2  | Completed | 2026-03-30 05:07 PM | 2026-03-30 05:09 PM | Add `test_extract_nextjs_rsc_payloads_basic`, `_empty`, `_escaped` tests to `tests/test_sources/test_collectors.py`. Use inline HTML strings (not fixtures yet). |
| 1.3  | Completed | 2026-03-30 05:09 PM | 2026-03-30 05:09 PM | Run `pytest tests/test_sources/test_collectors.py` — all pass (38 passed). |
| 1.4  | Completed | 2026-03-30 05:09 PM | 2026-03-30 05:09 PM | Run `ruff check` and `ruff format --check` — clean. |
| 1.5  | Completed | 2026-03-30 05:10 PM | 2026-03-30 05:10 PM | Stage all Phase 1 changes. |
| 1.6  | Completed | 2026-03-30 05:10 PM | 2026-03-30 05:10 PM | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** Added `extract_nextjs_rsc_payloads()` to `ai_benchmark/sources/base.py`, 3 unit tests to `tests/test_sources/test_collectors.py`.
- **Changes hosted at:** TBD
- **Commit:** `add extract_nextjs_rsc_payloads() utility for Next.js RSC streaming pages`

## Phase 2: Mistral HTML Fixtures

**Goal:** Real HTML snapshots from the three extractable Mistral pages are saved as test fixtures.
**Depends on:** Phase 1 (utility function exists to validate fixtures contain RSC payloads).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1  | Completed | 2026-03-30 05:11 PM | 2026-03-30 05:11 PM | Create `tests/test_sources/fixtures/` directory. |
| 2.2  | Completed | 2026-03-30 05:12 PM | 2026-03-30 05:12 PM | Fetch `https://docs.mistral.ai/getting-started/changelog` and save to `tests/test_sources/fixtures/mistral_changelog.html`. |
| 2.3  | Completed | 2026-03-30 05:12 PM | 2026-03-30 05:12 PM | Fetch `https://mistral.ai/news/` and save to `tests/test_sources/fixtures/mistral_news.html`. |
| 2.4  | Completed | 2026-03-30 05:12 PM | 2026-03-30 05:12 PM | Fetch `https://docs.mistral.ai/models` and save to `tests/test_sources/fixtures/mistral_models.html`. |
| 2.5  | Completed | 2026-03-30 05:13 PM | 2026-03-30 05:14 PM | Verify each fixture contains `self.__next_f.push` calls (129, 45, 105 respectively). Also improved RSC regex in base.py to handle nested brackets in payloads. |
| 2.6  | Completed | 2026-03-30 05:15 PM | 2026-03-30 05:15 PM | Stage all Phase 2 changes. |
| 2.7  | Completed | 2026-03-30 05:15 PM | 2026-03-30 05:15 PM | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** Created `tests/test_sources/fixtures/` with 3 HTML fixtures (743KB, 204KB, 642KB). Fixed RSC regex in `base.py` to properly handle escaped quotes and nested brackets — matches all 129/45/105 payloads in real fixtures vs ~2 with original regex.
- **Changes hosted at:** TBD
- **Commit:** `add Mistral HTML fixtures, fix RSC regex for nested bracket payloads`

## Phase 3: Mistral Changelog Extraction

**Goal:** `MistralCollector._extract_changelog()` extracts items from RSC payloads with correct badge-type classification and date extraction.
**Depends on:** Phase 2 (changelog fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1  | Completed | 2026-03-30 05:20 PM | 2026-03-30 05:28 PM | Rewrite `_extract_changelog()` in `ai_benchmark/sources/mistral.py`. Extracts date/badge-type/text from serialized React virtual DOM via regex. Added `_is_content_text()`, `_clean_rsc_text()`, `_split_changelog_by_badges()`, `_extract_rsc_text_content()` helpers. Falls back to DOM selectors when no RSC payloads. |
| 3.2  | Completed | 2026-03-30 05:28 PM | 2026-03-30 05:30 PM | Add `test_mistral_changelog_extraction` — asserts 20+ items with 10+ model_release, 5+ api_update. |
| 3.3  | Completed | 2026-03-30 05:28 PM | 2026-03-30 05:30 PM | Add `test_mistral_changelog_date_extraction` — asserts 20+ items with YYYY-MM-DD dates. |
| 3.4  | Completed | 2026-03-30 05:28 PM | 2026-03-30 05:30 PM | Add `test_mistral_fallback_on_empty_rsc` — DOM-based fallback works on plain HTML. |
| 3.5  | Completed | 2026-03-30 05:30 PM | 2026-03-30 05:30 PM | Run `pytest tests/test_sources/test_collectors.py` — 41 passed. |
| 3.6  | Completed | 2026-03-30 05:30 PM | 2026-03-30 05:31 PM | Run `ruff check` and `ruff format --check` — clean. |
| 3.7  | Completed | 2026-03-30 05:31 PM | 2026-03-30 05:31 PM | Stage all Phase 3 changes. |
| 3.8  | Completed | 2026-03-30 05:31 PM | 2026-03-30 05:31 PM | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** Rewrote `MistralCollector._extract_changelog()` to parse RSC payloads (56 items from real fixture: 33 model_release, 18 api_update, 5 changelog_entry — all with dates). Added text content filtering to exclude CSS class strings, React internals, and badge labels. DOM-based fallback preserved. 3 new tests.
- **Changes hosted at:** TBD
- **Commit:** `rewrite Mistral changelog extraction to parse Next.js RSC payloads`

## Phase 4: Mistral News Extraction

**Goal:** `MistralCollector._extract_news()` extracts news posts from RSC payloads with resolved absolute URLs.
**Depends on:** Phase 2 (news fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1  | Completed | 2026-03-30 05:36 PM | 2026-03-30 05:40 PM | Rewrite `_extract_news()` to parse `"posts":[...]` JSON array from RSC payloads. Extracts slug, title, date (ISO), category, description. Resolves URLs to `https://mistral.ai/news/[slug]`. 64 posts extracted from fixture. |
| 4.2  | Completed | 2026-03-30 05:40 PM | 2026-03-30 05:41 PM | Add `test_mistral_news_extraction` — asserts 10+ items, all news_post type, Mistral in titles. |
| 4.3  | Completed | 2026-03-30 05:40 PM | 2026-03-30 05:41 PM | Add `test_mistral_news_url_resolution` — all URLs start with `https://mistral.ai/news/`. |
| 4.4  | Completed | 2026-03-30 05:41 PM | 2026-03-30 05:41 PM | Run `pytest tests/test_sources/test_collectors.py` — 43 passed. |
| 4.5  | Completed | 2026-03-30 05:41 PM | 2026-03-30 05:41 PM | Run `ruff check` and `ruff format --check` — clean. |
| 4.6  | Completed | 2026-03-30 05:42 PM |  | Stage all Phase 4 changes. |
| 4.7  | Completed | 2026-03-30 05:42 PM |  | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** Rewrote `MistralCollector._extract_news()` to parse structured JSON posts array from RSC payloads. Extracts 64 news posts with title, slug, date, category, and description. Added `_parse_json_array()` helper. 2 new tests.
- **Changes hosted at:** TBD
- **Commit:** `rewrite Mistral news extraction to parse Next.js RSC payloads`

## Phase 5: Mistral Models + Pricing Extraction

**Goal:** `MistralCollector._extract_model_docs()` extracts model entries from RSC payloads. `_extract_pricing()` upgraded best-effort.
**Depends on:** Phase 2 (models fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1  | Completed | 2026-03-30 05:44 PM | 2026-03-30 05:48 PM | Rewrite `_extract_model_docs()`. Extracts h3 model names and description text from RSC payloads. Deduplicates by name, skips nav headings. 30+ models from fixture. |
| 5.2  | Completed | 2026-03-30 05:48 PM | 2026-03-30 05:49 PM | Add `test_mistral_models_rsc_extraction` — asserts 10+ models with model_hint, Mistral and Codestral present. |
| 5.3  | Completed | 2026-03-30 05:48 PM | 2026-03-30 05:49 PM | Updated `_extract_pricing()` with comment — DOM approach retained, RSS captures pricing changes. |
| 5.4  | Completed | 2026-03-30 05:49 PM | 2026-03-30 05:49 PM | Run `pytest tests/test_sources/test_collectors.py` — 44 passed. |
| 5.5  | Completed | 2026-03-30 05:49 PM | 2026-03-30 05:49 PM | Run `ruff check` and `ruff format --check` — clean. |
| 5.6  | Completed | 2026-03-30 05:50 PM |  | Stage all Phase 5 changes. |
| 5.7  | Completed | 2026-03-30 05:50 PM |  | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** Rewrote `_extract_model_docs()` to extract model names from h3 headings in RSC payloads with descriptions and model_hint. Pricing extraction unchanged (DOM + RSS). 1 new test.
- **Changes hosted at:** TBD
- **Commit:** `rewrite Mistral models/pricing extraction to parse Next.js RSC payloads`

## Phase 6: Cohere RSS-Only Designation + Integration Verification

**Goal:** Cohere pages documented as RSS-only in `sources.toml`. Debug logging added. Full Mistral collection verified.
**Depends on:** Phase 5 (all Mistral extraction methods complete).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1  | Open   |               |                  | Add `notes` fields to 4 Cohere HTML pages in `ai_benchmark/config/sources.toml:232-251` documenting JS-rendered shells and RSS-only status. |
| 6.2  | Open   |               |                  | Add structlog import and debug logging to `CohereCollector.extract_items()` in `ai_benchmark/sources/cohere.py` for non-RSS pages returning 0 items. |
| 6.3  | Open   |               |                  | Add `test_cohere_html_returns_empty` to `tests/test_sources/test_collectors.py` — regression test confirming Cohere HTML methods return empty lists. |
| 6.4  | Open   |               |                  | Run full test suite: `pytest` — all pass. |
| 6.5  | Open   |               |                  | Run `ruff check` and `ruff format --check` — clean. |
| 6.6  | Open   |               |                  | Integration: run `ai-benchmark collect --source "Mistral AI"` and `ai-benchmark status` to verify Mistral pages now contribute items beyond RSS. |
| 6.7  | Open   |               |                  | Stage all Phase 6 changes. |
| 6.8  | Open   |               |                  | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `mark Cohere pages as RSS-only, verify Mistral RSC extraction end-to-end`
