# Mistral/Cohere HTML Parser Fixes Design Document

## 1. Purpose

The Mistral AI and Cohere source collectors have HTML parsers that return 0 items for all non-RSS pages. Both collectors were written with generic CSS selectors (`section, h2, h3, li`) that assume traditional server-rendered HTML. In practice, both sites use JavaScript frameworks (Next.js, Mintlify) that deliver content through non-standard mechanisms. All events for both sources currently come exclusively from Google News RSS fallback feeds.

This document analyzes which pages are fixable without introducing a headless browser dependency, and proposes an extraction strategy for those that are.

## 2. Scope

This design covers the HTML extraction layer for Mistral AI (5 HTML pages) and Cohere (4 HTML pages). It does not propose changes to the collection framework, processing pipeline, scheduling, or any other source collector. The RSS feeds for both sources already work and are out of scope.

The analysis distinguishes between pages where content is present in the HTTP response (extractable) and pages where the response is an empty JavaScript shell (not extractable without a browser).

## 3. Root Cause Analysis

### 3.1 Mistral AI

Mistral uses Next.js with React Server Components (RSC). The HTTP response contains actual content, but not in traditional HTML elements. Instead, content appears in two forms:

1. **RSC streaming payload.** The HTML contains `<script>` tags with `self.__next_f.push()` calls. These carry serialized React component trees as text. The actual titles, dates, descriptions, and URLs are embedded as string literals within these payloads. Standard BeautifulSoup CSS selectors find nothing because the content is inside JavaScript, not DOM elements.

2. **Streamed HTML fragments.** Some pages (changelog, models) include partial HTML within the RSC stream — `<li>` elements with `data-badge-type` attributes, `<h3>` tags, etc. These fragments are interspersed with RSC framing and are often nested inside `<script>` payloads rather than being direct children of `<body>`.

The current `MistralCollector` (`sources/mistral.py:35-105`) uses selectors like `soup.select("section, h2, h3, li, .changelog-entry")` which search the top-level DOM. They correctly identify the tag types but find no matching elements because the content is inside `<script>` text nodes.

**Pages and extractability:**

| Page | URL | Content mechanism | Extractable? |
|------|-----|-------------------|-------------|
| changelog | `docs.mistral.ai/getting-started/changelog` | RSC stream with `<li>` fragments and `data-badge-type` attributes | Yes |
| news | `mistral.ai/news/` | `self.__next_f.push()` with serialized post objects (title, href, date, description) | Yes |
| pricing | `mistral.ai/pricing` | Unknown (likely JS tables) | Needs verification |
| pricing (studio) | `docs.mistral.ai/deployment/ai-studio/pricing` | RSC stream | Needs verification |
| models | `docs.mistral.ai/models` | RSC stream with `<h3>` titles, `<p>` descriptions, badge attributes | Yes |

### 3.2 Cohere

Cohere uses two different frameworks: the main site (`cohere.com`) uses Next.js with Sanity CMS as the headless backend, and the docs site (`docs.cohere.com`) uses Mintlify. Both return near-empty HTML shells to plain HTTP requests.

The HTTP response for `cohere.com/blog` is a Next.js shell with no article content — Sanity CMS content is fetched client-side via JavaScript. The response for `docs.cohere.com/changelog` is a Mintlify shell with a loading spinner and no changelog entries. Unlike Mistral, there is no RSC streaming payload containing the actual content.

The current `CohereCollector` (`sources/cohere.py:31-94`) uses the same generic selector pattern as Mistral. Even with perfect selectors, no content would be found because the HTML genuinely contains none.

**Pages and extractability:**

| Page | URL | Content mechanism | Extractable? |
|------|-----|-------------------|-------------|
| release notes | `docs.cohere.com/changelog` | Mintlify JS shell, empty body | No |
| blog | `cohere.com/blog` | Next.js + Sanity CMS, client-side fetch | No |
| pricing | `cohere.com/pricing` | Next.js shell | No (likely) |
| models | `docs.cohere.com/docs/models` | Mintlify JS shell | No (likely) |

No native RSS or Atom feeds exist for either Mistral or Cohere. Tested `/feed`, `/rss`, `/rss.xml`, `/feed.xml`, `/atom.xml` on both domains — all return 404.

## 4. Core Design Principle

**Extract what the server sends; don't simulate what the browser does.** If content is present in the HTTP response — even embedded in JavaScript payloads — we extract it with regex and string parsing. If the server sends an empty shell that requires JavaScript execution to populate, we mark the page as RSS-only and do not attempt extraction. This avoids introducing a headless browser (Playwright, Selenium) which would add significant complexity, resource consumption, and fragility.

## 5. Proposed Approach

### 5.1 Mistral: Next.js RSC Payload Extraction

Create a shared utility function that extracts text content from `self.__next_f.push()` payloads in HTML. The function:

1. Uses regex to find all `self.__next_f.push([...])` calls in the HTML
2. Extracts the string arguments (which contain serialized React component data)
3. Provides the concatenated text for downstream parsing

Each Mistral extraction method then applies page-specific parsing to the extracted RSC text:

- **Changelog:** Parse `<li>` fragments within the RSC payload. Extract `data-badge-type` attributes (MODEL RELEASED, API UPDATED, etc.) for event classification. Extract date headings and entry descriptions.
- **News:** Extract serialized post objects from the RSC payload. These contain `href`, title text, date strings, and description strings as recognizable patterns within the serialized data.
- **Models:** Extract `<h3>` model names and `<p>` descriptions from the RSC stream fragments.
- **Pricing:** Attempt extraction; if the pricing page uses traditional `<table>` elements within the RSC stream, the existing `_extract_pricing()` may work with minor selector adjustments. If not, defer to RSS.

### 5.2 Cohere: RSS-Only Designation

Since Cohere's HTML pages return empty shells, the four non-RSS pages cannot be fixed at the extraction layer. Options:

1. **Accept RSS-only status.** The Google News RSS feed already captures Cohere announcements. Mark the HTML pages in `sources.toml` with a note indicating they are non-functional pending a headless browser or API integration. Optionally reduce their polling frequency or deprioritize them.

2. **Investigate Sanity CMS API.** Cohere's blog is backed by Sanity CMS. Sanity projects sometimes expose a public GROQ API endpoint at a predictable URL. If discovered, a dedicated API-based collector (like the GitHub or Semantic Scholar collectors that override `collect_page()`) could fetch blog posts directly. This is speculative and deferred.

3. **Investigate Mintlify API.** Mintlify docs sites sometimes have a JSON API for content. If `docs.cohere.com` exposes one, it could be used for release notes. Also speculative and deferred.

The recommended approach is option 1 (accept RSS-only) with notes in `sources.toml` for future investigation of options 2 and 3.

## 6. Functional Requirements

### 6.1 RSC Payload Extraction Utility

**R1.** A function `extract_nextjs_rsc_payloads(html: str) -> list[str]` that extracts all `self.__next_f.push()` payload strings from raw HTML. Placed in a shared location accessible to any collector that encounters Next.js RSC pages.

**R2.** The function handles edge cases: escaped quotes within payloads, multi-line payloads, nested bracket structures, and Unicode escape sequences.

**R3.** The function returns raw strings, not parsed structures. Page-specific parsing remains in each collector method.

### 6.2 Mistral Collector Fixes

**R4.** `_extract_changelog()` uses RSC payload extraction to find changelog entries with dates, badge types, and descriptions. Produces `RawItem` objects with `item_type` set based on badge type (model_release, api_update, changelog_entry).

**R5.** `_extract_news()` uses RSC payload extraction to find news post objects. Produces `RawItem` objects with title, URL (relative href resolved to absolute), date_text, and body.

**R6.** `_extract_model_docs()` uses RSC payload extraction to find model names and descriptions. Produces `RawItem` objects with model_hint set to the extracted model name.

**R7.** `_extract_pricing()` is tested against the actual RSC payload. If pricing data is present in the payload, update the method. If not, accept that pricing comes from RSS only.

**R8.** All extraction methods fall back gracefully: if no RSC payloads are found (e.g., the site changes rendering), return an empty list rather than crashing.

### 6.3 Cohere Source Configuration

**R9.** Add notes to the four Cohere HTML pages in `sources.toml` indicating they return empty JS shells and are non-functional for HTML extraction. The RSS feed remains the primary collection path.

**R10.** Optionally log a debug-level message when Cohere HTML extraction returns 0 items, noting that this is expected.

### 6.4 Testing

**R11.** Unit tests for the RSC payload extraction utility using sample HTML fixtures from actual Mistral pages.

**R12.** Unit tests for each Mistral extraction method using saved HTML samples, verifying that items are extracted with correct types, titles, and URLs.

**R13.** No new tests needed for Cohere since the change is documentation/configuration only.

## 7. Out of Scope

- Headless browser integration (Playwright, Selenium, Puppeteer)
- Cohere HTML extraction fixes (requires browser or API access)
- Changes to the collection framework, fetcher, or processing pipeline
- Changes to any other source collector
- New RSS feed sources for Mistral or Cohere
- Sanity CMS or Mintlify API investigation (future work)
