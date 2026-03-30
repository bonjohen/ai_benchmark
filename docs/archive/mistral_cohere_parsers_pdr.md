# Physical Design Requirements: Mistral/Cohere HTML Parser Fixes

**Source document:** `docs/mistral_cohere_parsers_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-30 (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|-------|----------|-------|
| `SourceCollector` ABC | `ai_benchmark/sources/base.py:58` | Base class, `extract_items()` interface, `_extract_google_news_rss()` helper |
| `RawItem` dataclass | `ai_benchmark/sources/base.py:44` | Output type for all extraction methods |
| `extract_title()` | `ai_benchmark/sources/base.py:28` | Title truncation utility |
| `MistralCollector` | `ai_benchmark/sources/mistral.py:15` | Existing class to modify (106 lines) |
| `CohereCollector` | `ai_benchmark/sources/cohere.py:15` | Existing class — minimal changes (notes only) |
| `PageConfig` | `ai_benchmark/config/settings.py` | Page type routing in `extract_items()` |
| `sources.toml` (Mistral) | `ai_benchmark/config/sources.toml:178-219` | 6 pages: changelog, news, pricing x2, models, RSS |
| `sources.toml` (Cohere) | `ai_benchmark/config/sources.toml:221-256` | 5 pages: release notes, blog, pricing, models, RSS |
| Test patterns | `tests/test_sources/test_collectors.py` | Existing collector test module with `SourceConfig`/`PageConfig` fixture patterns |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---------|---------|--------------------|
| (none) | All parsing uses `re` (stdlib) and `BeautifulSoup` (already installed) | — |

## 2. Package Layout

No new files are added to the package. Changes are confined to:

```
ai_benchmark/
  sources/
    base.py             + extract_nextjs_rsc_payloads() utility function (~30 lines)
    mistral.py           rewrite 4 extraction methods (~120 lines replacing ~70 lines)
    cohere.py            add debug logging for expected-empty pages (~5 lines)
  config/
    sources.toml         add notes to 4 Cohere page entries (~4 lines)
tests/
  test_sources/
    test_collectors.py   + RSC extraction tests, Mistral extraction tests (~100 lines)
    fixtures/            (new directory) saved HTML samples for test fixtures
      mistral_changelog.html
      mistral_news.html
      mistral_models.html
```

## 3. RSC Payload Extraction Utility

### 3.1 Location

Add to `ai_benchmark/sources/base.py` as a module-level function, alongside `extract_title()`. This keeps shared extraction utilities in one place. All collectors already import from `base.py`.

### 3.2 Function Signature

```python
def extract_nextjs_rsc_payloads(html: str) -> list[str]:
    """Extract text content from Next.js React Server Component streaming payloads.

    Finds all self.__next_f.push([...]) calls in <script> tags and returns
    the string payloads. These contain serialized React component trees with
    embedded text content (titles, dates, descriptions, URLs).
    """
```

### 3.3 Implementation Approach

1. Use `re.findall()` with pattern `r'self\.__next_f\.push\(\[.*?\]\)'` (with `re.DOTALL`) to find all push calls.
2. For each match, extract the array argument content between `push([` and `])`.
3. The array contains a type indicator (integer) followed by a string payload. Extract the string portion.
4. Handle escaped characters: `\"`, `\\`, `\n`, `\t`, `\uXXXX`.
5. Return the list of decoded payload strings.

### 3.4 Extraction from RSC Payloads

RSC payloads contain a mix of:
- HTML fragments (e.g., `<li data-badge-type=\"MODEL RELEASED\">...</li>`)
- Serialized text content with field separators
- URL paths (e.g., `/news/mistral-large-2`)
- Date strings (e.g., `2026-03-15`)

To extract structured data from these payloads:
- **For HTML fragments:** Re-parse with BeautifulSoup against the concatenated payload text. This recovers the `<li>`, `<h3>`, `<a>` elements that the top-level parse misses.
- **For serialized text:** Use regex patterns specific to each page type (e.g., URL patterns like `/news/[slug]` followed by title text).

## 4. Mistral Collector Changes

### 4.1 `_extract_changelog()` (line 35)

**Current:** `soup.select("section, h2, h3, li, .changelog-entry")` — finds nothing.

**New approach:**
1. Call `extract_nextjs_rsc_payloads(html)` to get payload strings.
2. Concatenate all payloads into a single text blob.
3. Re-parse with `BeautifulSoup(payload_text, "lxml")` to find `<li>` elements.
4. For each `<li>`:
   - Extract `data-badge-type` attribute for event classification.
   - Extract text content for title and body.
5. Also search for date patterns (`YYYY-MM-DD` or month-name formats) in the payload to populate `date_text`.
6. Map badge types: `MODEL RELEASED` → `model_release`, `API UPDATED` → `api_update`, others → `changelog_entry`.

**Fallback:** If `extract_nextjs_rsc_payloads()` returns empty, fall back to the existing DOM-based approach (in case Mistral changes rendering).

### 4.2 `_extract_news()` (line 57)

**Current:** `soup.select("article, a[href*='/news/'], .post-card")` — finds nothing.

**New approach:**
1. Call `extract_nextjs_rsc_payloads(html)`.
2. Concatenate payloads and search for news post patterns:
   - URL pattern: regex `r'/news/[\w-]+'` to find post slugs.
   - Title/description: text surrounding or following URL references.
3. Re-parse concatenated payload with BeautifulSoup to find `<a href="/news/...">` links with adjacent text.
4. For each discovered post:
   - Resolve relative URL to `https://mistral.ai/news/[slug]`.
   - Extract title from link text or adjacent heading element.
   - Extract date from nearby date patterns.
   - Set `item_type="news_post"`.

**Fallback:** If no RSC payloads found, fall back to existing selectors.

### 4.3 `_extract_model_docs()` (line 76)

**Current:** `soup.select("tr, .model-card, section, h3")` — finds nothing.

**New approach:**
1. Call `extract_nextjs_rsc_payloads(html)`.
2. Re-parse concatenated payload with BeautifulSoup.
3. Find `<h3>` elements (model names) and adjacent `<p>` elements (descriptions).
4. Extract badge/tag information if present.
5. For each model entry:
   - Set `title` to model name.
   - Set `model_hint` to the model name (enables slug extraction downstream).
   - Set `body` to description text.
   - Set `item_type="model_entry"`.

**Fallback:** If no RSC payloads found, fall back to existing selectors.

### 4.4 `_extract_pricing()` (line 91)

**Current approach:** `soup.select("tr")` looking for table rows with `<td>`/`<th>` cells.

**Assessment needed:** The pricing page may or may not embed `<table>` elements in the RSC payload. The implementation should:
1. First try the existing DOM-based approach (in case the page has standard tables).
2. If no results, try RSC payload extraction and re-parse for table elements.
3. If still no results, return empty (pricing captured via RSS).

This is the lowest-priority page since pricing changes are also captured by Google News RSS.

### 4.5 `extract_items()` Routing (line 22)

No changes needed. The existing routing logic correctly dispatches by `page.page_type` and handles RSS separately. Each extraction method change is internal to its own method.

## 5. Cohere Collector Changes

### 5.1 HTML Extraction Methods

No functional changes. The four extraction methods (`_extract_release_notes`, `_extract_blog`, `_extract_pricing`, `_extract_model_docs`) will continue to return empty lists for HTML pages. This is correct behavior — the HTML genuinely contains no content.

### 5.2 Debug Logging (Optional)

Add a debug-level log message to the Cohere `extract_items()` method when a non-RSS page returns 0 items:

```python
def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
    if "rss" in page.page_type:
        return self._extract_google_news_rss(html)
    items = self._dispatch_by_type(page, html)
    if not items:
        logger.debug(
            "cohere_html_extraction_empty",
            page_type=page.page_type,
            note="Expected: Cohere pages are JS-rendered shells. RSS is primary.",
        )
    return items
```

This prevents false alarms in logs and documents the expected behavior.

### 5.3 Source Catalog Notes

Add `notes` fields to the 4 Cohere HTML page entries in `sources.toml`:

```toml
[[sources.pages]]
canonical_url = "https://docs.cohere.com/changelog"
page_type = "release notes"
polling_frequency = "daily"
notes = "Mintlify JS shell - returns empty HTML. RSS feed is primary collection path."

[[sources.pages]]
canonical_url = "https://cohere.com/blog"
page_type = "blog"
polling_frequency = "daily"
notes = "Next.js + Sanity CMS - returns empty HTML. RSS feed is primary collection path."

[[sources.pages]]
canonical_url = "https://cohere.com/pricing"
page_type = "pricing"
polling_frequency = "daily"
notes = "Next.js shell - returns empty HTML. RSS feed is primary collection path."

[[sources.pages]]
canonical_url = "https://docs.cohere.com/docs/models"
page_type = "model catalog"
polling_frequency = "daily"
notes = "Mintlify JS shell - returns empty HTML. RSS feed is primary collection path."
```

## 6. Test Plan

### 6.1 Fixture Preparation

Before writing tests, capture actual HTML responses from the three extractable Mistral pages:
- `https://docs.mistral.ai/getting-started/changelog`
- `https://mistral.ai/news/`
- `https://docs.mistral.ai/models`

Save as fixtures in `tests/test_sources/fixtures/`. These are static snapshots used for deterministic testing. Each fixture should be a real response (not hand-crafted) to ensure the extraction logic handles actual RSC payload formatting.

### 6.2 Unit Tests

| Test | Verifies |
|------|----------|
| `test_extract_nextjs_rsc_payloads_basic` | Extracts payload strings from sample HTML with `self.__next_f.push()` calls |
| `test_extract_nextjs_rsc_payloads_empty` | Returns empty list for HTML without RSC payloads |
| `test_extract_nextjs_rsc_payloads_escaped` | Handles escaped quotes and Unicode within payloads |
| `test_mistral_changelog_extraction` | `_extract_changelog()` returns items from fixture HTML with correct badge types |
| `test_mistral_changelog_date_extraction` | Extracted changelog items include date_text where available |
| `test_mistral_news_extraction` | `_extract_news()` returns news posts from fixture HTML with titles and URLs |
| `test_mistral_news_url_resolution` | News post URLs are resolved to absolute `https://mistral.ai/news/...` paths |
| `test_mistral_models_extraction` | `_extract_model_docs()` returns model entries with model_hint set |
| `test_mistral_fallback_on_empty_rsc` | All extraction methods fall back gracefully when no RSC payloads found |
| `test_cohere_html_returns_empty` | Cohere HTML extraction methods return empty lists (regression test) |

### 6.3 Integration Verification

After implementation, run a single-source collection to verify:

```bash
ai-benchmark collect --source "Mistral AI"
ai-benchmark status
```

Compare Mistral event counts before and after. The changelog, news, and models pages should now contribute items beyond what RSS provides.

## 7. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Mistral changes RSC payload format | Medium (Next.js updates) | Fallback to existing selectors; RSC extraction is additive |
| RSC payload regex misses edge cases | Medium | Test against real fixtures; iterate on regex |
| Extracted items duplicate RSS items | High | Existing dedup pipeline handles this (title + org + date composite key) |
| Performance impact of RSC regex | Low | Pages are small (< 500KB); regex runs once per page fetch |
| Cohere adds server-side rendering later | Low | Existing selectors would start working; RSC extraction not needed |

## 8. Implementation Order

1. Add `extract_nextjs_rsc_payloads()` to `base.py` with unit tests
2. Capture HTML fixtures from live Mistral pages
3. Rewrite `MistralCollector._extract_changelog()` with tests
4. Rewrite `MistralCollector._extract_news()` with tests
5. Rewrite `MistralCollector._extract_model_docs()` with tests
6. Update `MistralCollector._extract_pricing()` (best-effort)
7. Add Cohere `sources.toml` notes and optional debug logging
8. Integration test: full collection run for Mistral AI
