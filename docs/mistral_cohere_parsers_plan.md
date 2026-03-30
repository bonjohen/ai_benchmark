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
| 1.5  | Started | 2026-03-30 05:10 PM |                  | Stage all Phase 1 changes. |
| 1.6  | Open   |               |                  | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** Added `extract_nextjs_rsc_payloads()` to `ai_benchmark/sources/base.py`, 3 unit tests to `tests/test_sources/test_collectors.py`.
- **Changes hosted at:** TBD
- **Commit:** `add extract_nextjs_rsc_payloads() utility for Next.js RSC streaming pages`

## Phase 2: Mistral HTML Fixtures

**Goal:** Real HTML snapshots from the three extractable Mistral pages are saved as test fixtures.
**Depends on:** Phase 1 (utility function exists to validate fixtures contain RSC payloads).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1  | Open   |               |                  | Create `tests/test_sources/fixtures/` directory. |
| 2.2  | Open   |               |                  | Fetch `https://docs.mistral.ai/getting-started/changelog` and save to `tests/test_sources/fixtures/mistral_changelog.html`. |
| 2.3  | Open   |               |                  | Fetch `https://mistral.ai/news/` and save to `tests/test_sources/fixtures/mistral_news.html`. |
| 2.4  | Open   |               |                  | Fetch `https://docs.mistral.ai/models` and save to `tests/test_sources/fixtures/mistral_models.html`. |
| 2.5  | Open   |               |                  | Verify each fixture contains `self.__next_f.push` calls (sanity check that RSC payloads are present). |
| 2.6  | Open   |               |                  | Stage all Phase 2 changes. |
| 2.7  | Open   |               |                  | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `add Mistral HTML fixtures for RSC payload extraction tests`

## Phase 3: Mistral Changelog Extraction

**Goal:** `MistralCollector._extract_changelog()` extracts items from RSC payloads with correct badge-type classification and date extraction.
**Depends on:** Phase 2 (changelog fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1  | Open   |               |                  | Rewrite `_extract_changelog()` in `ai_benchmark/sources/mistral.py:35`. Call `extract_nextjs_rsc_payloads()`, concatenate, re-parse with BeautifulSoup, extract `<li>` elements with `data-badge-type`. Fall back to existing selectors if no RSC payloads. |
| 3.2  | Open   |               |                  | Add `test_mistral_changelog_extraction` using changelog fixture — asserts items returned with correct `item_type` values (model_release, api_update, changelog_entry). |
| 3.3  | Open   |               |                  | Add `test_mistral_changelog_date_extraction` — asserts `date_text` populated where dates are present in payload. |
| 3.4  | Open   |               |                  | Add `test_mistral_fallback_on_empty_rsc` — `_extract_changelog()` with plain HTML (no RSC) falls back gracefully. |
| 3.5  | Open   |               |                  | Run `pytest tests/test_sources/test_collectors.py` — all pass. |
| 3.6  | Open   |               |                  | Run `ruff check` and `ruff format --check` — clean. |
| 3.7  | Open   |               |                  | Stage all Phase 3 changes. |
| 3.8  | Open   |               |                  | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `rewrite Mistral changelog extraction to parse Next.js RSC payloads`

## Phase 4: Mistral News Extraction

**Goal:** `MistralCollector._extract_news()` extracts news posts from RSC payloads with resolved absolute URLs.
**Depends on:** Phase 2 (news fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1  | Open   |               |                  | Rewrite `_extract_news()` in `ai_benchmark/sources/mistral.py:57`. Call `extract_nextjs_rsc_payloads()`, re-parse, find `<a href="/news/...">` links and adjacent text. Resolve relative URLs to `https://mistral.ai/news/[slug]`. Fall back to existing selectors if no RSC payloads. |
| 4.2  | Open   |               |                  | Add `test_mistral_news_extraction` using news fixture — asserts items returned with titles and `item_type="news_post"`. |
| 4.3  | Open   |               |                  | Add `test_mistral_news_url_resolution` — asserts extracted URLs are absolute `https://mistral.ai/news/...` paths. |
| 4.4  | Open   |               |                  | Run `pytest tests/test_sources/test_collectors.py` — all pass. |
| 4.5  | Open   |               |                  | Run `ruff check` and `ruff format --check` — clean. |
| 4.6  | Open   |               |                  | Stage all Phase 4 changes. |
| 4.7  | Open   |               |                  | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `rewrite Mistral news extraction to parse Next.js RSC payloads`

## Phase 5: Mistral Models + Pricing Extraction

**Goal:** `MistralCollector._extract_model_docs()` extracts model entries from RSC payloads. `_extract_pricing()` upgraded best-effort.
**Depends on:** Phase 2 (models fixture exists).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1  | Open   |               |                  | Rewrite `_extract_model_docs()` in `ai_benchmark/sources/mistral.py:76`. Call `extract_nextjs_rsc_payloads()`, re-parse, find `<h3>` model names and `<p>` descriptions. Set `model_hint`. Fall back to existing selectors. |
| 5.2  | Open   |               |                  | Add `test_mistral_models_extraction` using models fixture — asserts items returned with `model_hint` set and `item_type="model_entry"`. |
| 5.3  | Open   |               |                  | Update `_extract_pricing()` in `ai_benchmark/sources/mistral.py:91` — try existing DOM approach first, then RSC payload extraction, then return empty. |
| 5.4  | Open   |               |                  | Run `pytest tests/test_sources/test_collectors.py` — all pass. |
| 5.5  | Open   |               |                  | Run `ruff check` and `ruff format --check` — clean. |
| 5.6  | Open   |               |                  | Stage all Phase 5 changes. |
| 5.7  | Open   |               |                  | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** TBD
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
