# Playwright Fetcher for Cloudflare-Blocked Pages — Implementation Plan

**Source document:** `docs/collection_errors_design.md` (§3.1, §3.5)

## Context

OpenAI (5 pages) and xAI (1 page) are primary sources blocked by Cloudflare managed challenges (`cf-mitigated: challenge`). These require JavaScript execution to solve. The httpx client cannot execute JS. Playwright launches a real Chromium browser that solves challenges automatically.

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed

### Commit Protocol

1. Work through all tasks in a phase.
2. Stage and commit all changes for the phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| Headless browser | `playwright` (async API, Chromium) |
| Install | `pip install playwright && playwright install chromium` |

---

## Phase 1: Playwright Fetcher

**Goal:** A PlaywrightFetcher class can fetch Cloudflare-protected pages by launching headless Chromium. The existing Fetcher delegates to it for pages marked as requiring a browser.
**Depends on:** Nothing.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Open | | | Add `playwright` to `pyproject.toml` optional dependencies under a `[browser]` extra. |
| 1.2 | Open | | | Create `ai_benchmark/collection/playwright_fetcher.py` — `PlaywrightFetcher` class with `async fetch(url) -> FetchResult`. Launch Chromium headless, navigate to URL, wait for Cloudflare challenge to resolve (wait for `cf-mitigated` to clear or body content to appear), return page HTML. Reuse browser instance across fetches. Close on `aclose()`. |
| 1.3 | Open | | | Modify `ai_benchmark/collection/fetcher.py` — add `use_browser: bool` parameter to `fetch()`. When True and PlaywrightFetcher is available, delegate to it instead of httpx. Gracefully fall back to httpx if playwright is not installed. |
| 1.4 | Open | | | Mark the 6 blocked pages in `config/sources.toml` with `browser = true` flag. |
| 1.5 | Open | | | Modify `coordination/coordinator.py` — pass the `browser` flag from page config through FetchTask to the fetcher, so only marked pages use Playwright. |
| 1.6 | Open | | | Create `tests/test_playwright_fetcher.py` — test FetchResult creation, test graceful fallback when playwright not installed, test browser flag propagation. |
| 1.7 | Open | | | Run `pytest` and `ruff check` — fix until green. |
| 1.8 | Open | | | Stage and commit. |

### Phase 1 Summary

- **Changes:** TBD
- **Commit:** `Add Playwright fetcher for Cloudflare-blocked pages`

---

## Phase 2: Install and Deploy

**Goal:** Playwright and Chromium are installed in the production venv. The 6 blocked pages are fetched successfully.
**Depends on:** Phase 1.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Install playwright in production venv: `pip install playwright && playwright install chromium`. |
| 2.2 | Open | | | Build wheel and install to `C:\ai-benchmark`. |
| 2.3 | Open | | | Test manually: `ai-benchmark collect --source OpenAI` — verify all 6 pages return 200 with real content. |
| 2.4 | Open | | | Test: `ai-benchmark collect --source xAI` — verify `x.ai/news` returns 200. |
| 2.5 | Open | | | Stage and commit. |

### Phase 2 Summary

- **Changes:** TBD
- **Commit:** `Deploy Playwright fetcher to production`
