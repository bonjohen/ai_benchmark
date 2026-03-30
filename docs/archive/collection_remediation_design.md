# Collection Pipeline Remediation — Design Document

## 1. Purpose

The ai_benchmark collection pipeline monitors 22 AI industry sources across 87 pages. The 2026-03-30 scheduled runs (AIBenchmarkCollect via Windows Task Scheduler) completed all 22 sources without crashes but revealed 9 issues causing data loss, performance degradation, and log noise. Five sources produce zero usable results. Research paper ingestion is severely degraded. This document analyzes each issue's root cause in the code and specifies concrete fixes.

## 2. Scope

Nine issues across five categories:

| # | Issue | Category | Items Lost / Run |
|---|-------|----------|-----------------|
| 1 | OpenAI — 403 on all 5 direct pages | External access | Pricing, models, system cards invisible |
| 2 | Semantic Scholar — 429 rate limited | External access | ~15 papers |
| 3 | Hugging Face Papers — quality filter drops all | Quality filter | ~47 papers |
| 4 | TechCrunch — RSS parse failure + 403 | External access | 0-20 articles (intermittent) |
| 5 | Hugging Face Forums — 0 events despite collected items | Quality filter + date parsing | ~30 forum topics |
| 6 | Hugging Face Leaderboard Docs — 0 items extracted | Broken collector | ~10-30 doc links |
| 7 | arXiv — cs.CL and cs.LG filtered as stale | Quality filter | ~35 papers |
| 8 | LMArena — 10-12 min processing bottleneck | Performance | None (runtime only) |
| 9 | XMLParsedAsHTMLWarning — cosmetic log noise | Cosmetic | None (noise only) |

**Out of scope:** collector rewrites for JS-rendered pages, new collector implementations, database data cleanup, headless browser integration.

## 3. Core Design Principles

1. **Fix the filter, not the symptom.** Issues 3, 5, and 7 share the same root cause in `quality_filter.py`. Fix the filter logic once rather than patching each collector individually.

2. **Collectors own their dates.** Each collector should populate `date_text` with whatever temporal signal the source provides. The quality filter should not rely on regex date extraction from `body` text for sources that inherently lack inline dates.

3. **Preserve the verification hierarchy.** The RSS fallback for OpenAI captures news but not pricing, model catalog, or system card changes. Acknowledge this gap explicitly.

4. **Graceful degradation over silent failure.** Rate-limited and blocked sources should log actionable diagnostics rather than silently returning 0 items.

## 4. Issue Analysis and Remediation

---

### Category A: Quality Filter False Positives

Issues 3, 5, and 7 share a common root cause in `processing/quality_filter.py`. The staleness check on lines 64-71 filters pages whose items lack a parseable recent date. The `dateless_page_types` exemption set on line 67 is:

```python
dateless_page_types = {"leaderboard", "model catalog", "pricing", "methodology"}
```

This set does not cover research paper listings (`"papers index"`, `"trending papers"`, `"recent submissions"`), forum topic lists (`"forum index"`), or documentation indexes (`"leaderboard docs"`). These page types inherently do not embed inline date strings that `extract_date()` can find.

The `has_recent_date()` function on lines 20-29 calls `extract_date(item.date_text or item.body)` for each item. When `date_text` is `None` (HF Papers, arXiv) or contains an ISO 8601 timestamp with a `T` separator (HF Forums), and `body` is empty or contains no date-like string, `extract_date()` returns `None` for every item, and the page is rejected.

---

### 4.1 Hugging Face Papers — Quality Filter Drops All Papers

**Symptoms.** Both HF Papers pages extract items (8 from `papers index`, 39 from `trending papers`) but all are filtered as `low_value_stale_dates`. Zero papers reach the triage pipeline. The `ai-benchmark status` command shows 0 papers for Hugging Face Papers.

**Root cause.** `HFPapersCollector.extract_items()` in `sources/research/hf_papers.py` (lines 49-60) creates `RawItem` objects without setting `date_text`. The `body` field contains the paper's title + abstract text, which does not contain a recognizable date string. In `quality_filter.py` line 26, `extract_date(item.date_text or item.body)` falls through to `extract_date(body_text)`. The regex-based date parser in `normalizer.py` line 513 (`\b(\d{4}-\d{2}-\d{2})\b`) does not find ISO dates in paper abstracts. The page type `"papers index"` is not in `dateless_page_types`, and this is not a cold start (prior snapshots exist), so the page is rejected.

**Recommended fix.** Two changes in `processing/quality_filter.py`:

**(a)** Expand `dateless_page_types` on line 67 to include research and forum page types:

```python
dateless_page_types = {
    "leaderboard", "model catalog", "pricing", "methodology",
    "papers index", "trending papers", "recent submissions",
    "forum index", "discourse json", "leaderboard docs",
}
```

**(b)** Add a broader exemption for pages producing only `candidate_paper` items. Before the staleness check on line 68, add:

```python
all_candidate_papers = items and all(i.item_type == "candidate_paper" for i in items)
skip_date_check = is_cold_start or (page.page_type in dateless_page_types) or all_candidate_papers
```

This ensures any page whose items are entirely research papers (destined for triage, not event creation) is never blocked by the staleness heuristic, regardless of page type.

**Impact.** Recovers ~47 papers per run. These feed the triage pipeline as `candidate_paper` items. Total paper discovery rises from 52 (arXiv cs.AI only) to ~99.

---

### 4.2 arXiv — cs.CL and cs.LG Lists Filtered as Stale

**Symptoms.** `cs.AI/recent` passes the filter (22 papers), but `cs.CL/recent` (25 papers) and `cs.LG/recent` (10 papers) are filtered as `low_value_stale_dates` every run.

**Root cause.** Identical to Issue 3. `ArxivCollector.extract_items()` in `sources/research/arxiv.py` (line 75) sets `body=authors` and does not set `date_text`. The page type `"recent submissions"` is not in `dateless_page_types`. The `cs.AI` page passes only because some author name or paper title coincidentally contains a date-like substring that `extract_date()` can parse.

**Recommended fix.** The `dateless_page_types` expansion in Issue 3's fix (a) handles this — `"recent submissions"` is included. Additionally, set `date_text` in the arXiv collector for defense-in-depth. In `sources/research/arxiv.py`, in the `RawItem` constructor (around line 75):

```python
from datetime import date as date_type

RawItem(
    title=title,
    url=arxiv_url,
    body=authors,
    date_text=date_type.today().isoformat(),  # /recent pages are inherently current
    item_type="candidate_paper",
    metadata={...},
)
```

**Impact.** Recovers ~35 papers per run. Combined with Issue 3 fix, total paper count rises from 52 to ~134.

---

### 4.3 Hugging Face Forums — 0 Events Despite Collected Items

**Symptoms.** The Discourse JSON endpoint (`discuss.huggingface.co/latest.json`) extracts 30 forum topics in Runs 2-3. The HTML page (`discuss.huggingface.co/`) also extracts 30 items but they're quality-filtered. The `ai-benchmark status` shows 0 events for HF Forums across all runs.

**Root cause.** Two interacting problems:

**(a) HTML path is quality-filtered.** The HTML page has page_type `"forum index"` which is not in `dateless_page_types`. Items from `extract_items()` (lines 102-156) have `body=""` and no `date_text`, so `extract_date("")` returns `None`. All 30 items are filtered as stale.

**(b) JSON path bypasses quality filter but has a date parsing bug.** The `collect_page()` override in `hf_forums.py` line 54-59 returns `(items, None)` directly for `"discourse json"` pages, bypassing `_collect_page_inner()` and its quality filter. The collector correctly sets `date_text=topic.get("created_at", "")` on line 88. Discourse returns ISO 8601 timestamps like `"2026-03-29T15:00:00.000Z"`.

However, when these items reach the processing pipeline, `extract_date()` in `normalizer.py` line 513 uses regex `\b(\d{4}-\d{2}-\d{2})\b`. In the string `"2026-03-29T15:00:00.000Z"`, the `T` immediately follows `29` — since `T` is a word character, the `\b` boundary does not match between `29` and `T`. The regex fails to extract the date. Events are created without a `published_date`, and may then be deduped or lost depending on the dedup logic's handling of null dates.

**(c) Silent failure on JSON fetch.** In Run 1 (5:00 AM), the JSON endpoint produced 0 items — likely the fetch failed but `collect_page()` returns `[], None` silently on line 57-58 with no logging.

**Recommended fix.** Three changes:

**(1)** Fix `extract_date()` in `processing/normalizer.py` to handle ISO 8601 timestamps with `T` separator. Insert before the existing regex on line 513:

```python
def extract_date(text: str) -> str | None:
    """Extract and normalize the first date found in text to YYYY-MM-DD."""
    # ISO 8601 with time component: 2026-03-29T15:00:00Z
    match = re.search(r"(\d{4}-\d{2}-\d{2})T", text)
    if match:
        return match.group(1)

    # Standard ISO date
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)
    # ... rest unchanged
```

**(2)** The `dateless_page_types` expansion in Issue 3's fix covers `"forum index"` and `"discourse json"`.

**(3)** Add logging for JSON fetch failures in `hf_forums.py`. Replace lines 57-58:

```python
if not result.ok:
    logger.warning(
        "discourse_fetch_failed",
        url=page.canonical_url,
        status=result.status_code,
        error=result.error,
    )
    return [], None
```

**Impact.** Recovers ~30 forum topic events per run. With the `extract_date` fix, ISO timestamps from the Discourse JSON are properly parsed, enabling accurate `published_date` values. The `extract_date` fix also benefits any other source that produces ISO 8601 timestamps (API-based collectors, RSS pubDate fields).

---

### Category B: Broken Collector

### 4.4 Hugging Face Leaderboard Docs — Always 0 Items

**Symptoms.** The page `huggingface.co/docs/leaderboards/en/index` consistently returns 0 items on every run.

**Root cause.** `HFLeaderboardDocsCollector.extract_items()` in `sources/community/hf_leaderboard_docs.py` line 29 uses CSS selectors:

```python
for card in soup.select("a[href*='/spaces/'], .space-card, article"):
```

These selectors target a Hugging Face Spaces directory layout (cards with `.space-card` class, links containing `/spaces/`). The actual URL is a **documentation page** (`/docs/leaderboards/en/index`) using the standard HF docs template. The DOM contains a sidebar navigation and main content area with links to individual leaderboard documentation pages. There are no `.space-card` elements, no `a[href*='/spaces/']` links, and the `article` selector matches zero elements in the docs template.

**Recommended fix.** Rewrite the CSS selectors to match the HF documentation page structure. The docs page contains a table of contents with links to individual leaderboard pages in the main content area.

```python
def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[RawItem] = []

    # HF docs pages: target links in the main content area
    main = soup.select_one("main, .doc-content, [role='main'], .prose")
    if main is None:
        main = soup

    seen_urls: set[str] = set()
    for link in main.select("a[href]"):
        href = str(link.get("href", ""))
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        # Filter for leaderboard-related doc links
        if "/docs/leaderboards/" not in href and "/spaces/" not in href:
            continue
        # Skip self-referential and anchor-only links
        if href.startswith("#") or href.endswith("/index"):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        items.append(
            RawItem(
                title=title,
                url=href,
                body=title,
                item_type="leaderboard_space",
                metadata={
                    "source": "hf_leaderboard_docs",
                    "confidence_tier": self.CONFIDENCE_TIER,
                },
            )
        )
    return items
```

**Important:** Before implementing, fetch the actual page and inspect the DOM to confirm the selector strategy. Run `ai-benchmark collect --source "Hugging Face"` with debug logging and examine the raw HTML snapshot.

Also add `"leaderboard docs"` to the `dateless_page_types` set (already included in Issue 3's fix).

**Impact.** Recovers ~10-30 doc links per run. Low volume but valuable as a meta-source for discovering new community-managed benchmark leaderboards on Hugging Face.

---

### Category C: External Access Failures

### 4.5 OpenAI — All 5 Direct Pages Return 403

**Symptoms.** Every run, all five OpenAI direct pages return HTTP 403 Forbidden:

- `openai.com/news/product-releases/`
- `platform.openai.com/docs/changelog`
- `platform.openai.com/docs/models`
- `openai.com/api/pricing/`
- `openai.com/index/system-cards/`

Collection depends entirely on the Google News RSS feed (100 items/run). Pricing changes, model catalog updates, and system cards are invisible.

**Root cause.** The `Fetcher` in `collection/fetcher.py` sends a Chrome-like User-Agent (line 53) with browser-mimicking headers (lines 36-48), but OpenAI has deployed a WAF that goes beyond User-Agent validation. The fetcher uses `httpx` with HTTP/2, which has different TLS fingerprints than real Chrome. The 403 response is terminal (no retry, lines 127-134) — correct behavior since retrying a WAF block is futile.

**Recommended fix.** Three mitigation strategies:

**(a) Accept the RSS-only baseline and document the gap.** Add comments in `config/sources.toml` (lines 17-44) marking the direct pages as `blocked_expected = true` or similar. In the collection log output, distinguish "blocked (expected)" from "broken (unexpected)" so persistent 403s do not appear as new action items each run. This could be a `notes` field on the page config:

```toml
[[sources.pages]]
canonical_url = "https://openai.com/news/product-releases/"
page_type = "product-news index"
polling_frequency = "daily"
notes = "Blocked by WAF since 2026-03. RSS fallback is primary collection path."
```

**(b) Add OpenAI API as a supplementary source.** OpenAI publishes model information via their REST API (`GET /v1/models`). Add a new page entry in `sources.toml` with `page_type = "api endpoint"` and add an API-based collection path in `openai.py` that calls the models endpoint with an API key. This recovers the model catalog without website scraping. Requires a new setting `AI_BENCH_OPENAI_API_KEY` in `config/settings.py`.

**(c) Browser automation (future work, out of scope).** A headless browser (Playwright) would bypass WAF detection for pricing and system cards. Note as the long-term solution but do not implement in this remediation.

**Impact.** Strategy (a) is documentation only. Strategy (b) recovers the model catalog (~40-60 models with metadata). Pricing, changelog, and system card pages remain uncollected until browser automation is implemented.

---

### 4.6 Semantic Scholar — 429 Rate Limited Every Run

**Symptoms.** All API requests to Semantic Scholar fail with HTTP 429 after 3 retries. Zero papers collected from S2 across all runs today.

**Root cause.** `SemanticScholarClient` in `sources/research/semantic_scholar.py` extends `APIClient` from `collection/api_client.py`. The auth header method (line 98-99 of `semantic_scholar.py`) sends `x-api-key` only if `api_key` is set. The `api_key` is read from `PipelineSettings.semantic_scholar_api_key` (`config/settings.py` line 62), which defaults to `None`. Without the key, all requests are unauthenticated, hitting the public tier (~1 req/sec with strict burst limits).

The `collect_via_api()` method (lines 61-86) issues queries from `_DEFAULT_QUERIES` (lines 19-23) sequentially. Each failing query retries 3 times with the `Retry-After` header (5 seconds). The public tier often requires 30-60 seconds between requests, so 3 retries with 5-second waits are insufficient.

**Recommended fix.** Two changes:

**(a) Add inter-query delays for unauthenticated mode.** In `sources/research/semantic_scholar.py`, modify `collect_via_api()` to add a delay between queries:

```python
async def collect_via_api(self, queries: list[str], limit: int = 5) -> list[RawItem]:
    items: list[RawItem] = []
    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(3.0)  # respect public tier rate limit
        try:
            results = await self.client.search_paper(query, limit=limit)
        except httpx.HTTPStatusError:
            logger.warning("semantic_scholar_query_failed", query=query)
            continue  # skip to next query instead of failing entire collection
        # ... rest of loop
```

Also increase the retry count for the S2 client specifically, and log whether an API key is configured at collection start:

```python
async def collect_page(self, page, fetcher, ...):
    if not self.client.api_key:
        logger.warning("semantic_scholar_no_api_key", hint="Set AI_BENCH_SEMANTIC_SCHOLAR_API_KEY for reliable collection")
    # ...
```

**(b) Document API key setup.** Add `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` to the `.env.example` and the README's Configuration table. The authenticated tier allows 100 req/sec, eliminating rate limiting entirely. Free API keys are available at https://www.semanticscholar.org/product/api#api-key.

**Impact.** With inter-query delays (no API key): ~10-15 papers/run. With API key: all 15 papers reliably. Combined with arXiv and HF Papers fixes, total research paper intake rises from 52 to ~149-164 per run.

---

### 4.7 TechCrunch — RSS Parse Issues + Main Page 403

**Symptoms.** The TechCrunch main page intermittently returns 403. The RSS feed intermittently fails XML parsing: Run 1 logs `rss_xml_parse_empty` (0 items), Runs 2-3 succeed (20 items).

**Root cause.** Two separate issues:

**(a) RSS parsing fragility.** `_extract_rss()` in `sources/news/techcrunch.py` (line 29) first tries `BeautifulSoup(xml_text, "lxml-xml")`. WordPress RSS feeds can include a UTF-8 BOM, CDATA sections with unescaped HTML, and encoding declarations that confuse the strict XML parser. When `lxml-xml` finds 0 `<item>` elements, the fallback on line 36 tries `BeautifulSoup(xml_text, "lxml")` — an HTML parser that treats `<item>` as unknown tags and does not find them via `find_all("item")`.

**(b) Main page 403.** TechCrunch uses CDN-level bot detection that intermittently blocks automated requests. The RSS feed is marked `priority = true` in `sources.toml` and is the primary collection path; the HTML page is supplementary.

**Recommended fix.**

**(a) Improve RSS resilience.** In `techcrunch.py`, strip BOM before parsing and add a regex-based last-resort extractor:

```python
def _extract_rss(self, xml_text: str) -> list[RawItem]:
    # Strip BOM if present
    clean = xml_text.lstrip("\ufeff").strip()
    soup = BeautifulSoup(clean, "lxml-xml")
    rss_items = soup.find_all("item")
    if not rss_items:
        logger.warning("rss_xml_parse_empty", parser="lxml-xml", source="techcrunch")
        # Fallback: try HTML parser with case-insensitive tag matching
        soup = BeautifulSoup(clean, "lxml")
        rss_items = soup.find_all("item")
    if not rss_items:
        # Last resort: regex extraction
        rss_items = self._regex_extract_rss(clean)
    # ... process rss_items
```

The regex fallback extracts `<title>`, `<link>`, `<pubDate>` using `re.findall(r"<item>(.*?)</item>", clean, re.DOTALL)` and parses each block.

Alternatively, add `feedparser` as an optional dependency. It is the standard Python library for RSS/Atom feeds and handles all encoding edge cases.

**(b) Mark the HTML page as expected-fallback.** Add a `notes` field in `sources.toml` documenting that the RSS feed is primary and the HTML page may intermittently fail.

**Impact.** Stabilizes TechCrunch collection at ~20 items per run. The HTML page remains intermittently available.

---

### Category D: Performance

### 4.8 LMArena — 10-12 Minute Processing Bottleneck

**Symptoms.** LMArena extracts 1,343 items across 8 leaderboard pages. Processing takes 6-10 minutes, dominating the 14-19 minute total collection run.

**Root cause.** `process_items()` in `processing/pipeline.py` (lines 164-187) processes items sequentially in a `for` loop. Each `process_item()` call performs:

1. Title normalization + model slug extraction (in-memory, fast)
2. `is_duplicate()` — async database query (I/O-bound)
3. `EventRecord` creation + `session.flush()` (I/O-bound)
4. `create_claim()` + flush (I/O-bound)
5. `update_confirmation_status()` with query (I/O-bound)
6. `build_cross_references()` with multiple queries (I/O-bound)

For 1,343 items, the cumulative I/O from sequential database operations dominates. The model slug extraction uses 53 regex patterns in `normalizer.py`, but this is CPU-bound and negligible compared to the DB operations.

**Recommended fix.** Three optimizations, applicable independently:

**(a) Batch deduplication pre-check.** Before the item loop, collect all normalized titles and model slugs, then execute a single `SELECT ... WHERE normalized_title IN (...)` query. Pass the results set into the loop so `is_duplicate()` checks the local cache first:

```python
async def process_items(session, items, organization, ...):
    # Pre-fetch existing events for batch dedup
    norm_titles = [normalize_title(item.title) for item in items]
    existing = await batch_find_duplicates(session, norm_titles, organization)
    existing_set = {e.normalized_title for e in existing}

    created = []
    for item in items:
        norm = normalize_title(item.title)
        if norm in existing_set:
            # Create claim on existing event, skip full dedup
            await create_claim_on_existing(session, existing_set[norm], item)
            continue
        event = await process_item(session, item, ...)
        if event:
            created.append(event)
    return created
```

This replaces ~1,343 individual dedup queries with 1 batch query + in-memory lookups.

**(b) Batch flush.** Instead of `session.flush()` after every event+claim creation, accumulate and flush every 50-100 items:

```python
for i, item in enumerate(items):
    event = await process_item_no_flush(session, item, ...)
    if i % 100 == 0:
        await session.flush()
await session.flush()  # final batch
```

**(c) Skip cross-references for same-source benchmark entries.** `build_cross_references()` queries for events with matching model slugs within a 7-day window. For 1,343 LMArena entries all observed at the same time, these queries are expensive and rarely productive (cross-refs are more useful across different sources). Add an early return:

```python
async def build_cross_references(session, event, source_config):
    if event.event_type == "benchmark_result" and source_config.classification == "secondary":
        return  # cross-refs built at query time for same-source benchmarks
    # ... existing logic
```

**Impact.** Optimization (a) alone should reduce LMArena processing from 6-10 minutes to ~2-3 minutes. Combined with (b) and (c), target is under 2 minutes. Total collection run time should drop from 14-19 minutes to ~5-8 minutes.

---

### Category E: Cosmetic

### 4.9 XMLParsedAsHTMLWarning — Log Noise

**Symptoms.** Every collection run produces an `XMLParsedAsHTMLWarning` traceback in the log, pointing to `collection/differ.py` line 40. Does not affect results.

**Root cause.** `clean_html()` in `differ.py` line 40 uses `BeautifulSoup(html, "lxml")` for all content. When RSS XML content passes through snapshot comparison, the HTML parser detects XML declarations or namespaces and issues the warning.

**Recommended fix.** Add XML detection in `clean_html()`:

```python
def clean_html(html: str, content_selectors: list[str] | None = None) -> str:
    stripped = html.lstrip()
    is_xml = (
        stripped.startswith("<?xml")
        or stripped.startswith("<rss")
        or stripped.startswith("<feed")
    )
    parser = "lxml-xml" if is_xml else "lxml"
    soup = BeautifulSoup(html, parser)
    # ... rest unchanged
```

Alternative quick fix — suppress the warning at module level:

```python
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
```

The parser detection approach is preferred because it also produces better text extraction from XML.

**Impact.** Eliminates ~6-10 warning tracebacks per run. No functional change.

---

## 5. Functional Requirements

### 5.1 Quality Filter Changes (`processing/quality_filter.py`)

- Expand `dateless_page_types` to include: `"papers index"`, `"trending papers"`, `"recent submissions"`, `"forum index"`, `"discourse json"`, `"leaderboard docs"`.
- Add `candidate_paper` item-type exemption so pages producing only research papers are never staleness-filtered.
- Existing filters (trivial change ratio, short title garbage) must remain unchanged.

### 5.2 Date Parsing Fix (`processing/normalizer.py`)

- `extract_date()` must handle ISO 8601 timestamps with `T` separator (e.g., `"2026-03-29T15:00:00.000Z"` → `"2026-03-29"`).
- Must not break existing date extraction for other formats.

### 5.3 Collector Fixes

- **arXiv** (`sources/research/arxiv.py`): Set `date_text` to today's ISO date on all `RawItem` objects.
- **HF Forums** (`sources/community/hf_forums.py`): Add logging for JSON fetch failures.
- **HF Leaderboard Docs** (`sources/community/hf_leaderboard_docs.py`): Rewrite CSS selectors to match HF documentation page DOM structure. Verify against actual page before implementing.
- **Semantic Scholar** (`sources/research/semantic_scholar.py`): Add inter-query delays, log missing API key warning, handle per-query failures gracefully.
- **TechCrunch** (`sources/news/techcrunch.py`): Strip BOM before RSS parsing, add regex fallback for malformed XML.

### 5.4 Pipeline Performance (`processing/pipeline.py`)

- Batch deduplication pre-check before the item processing loop.
- Batch session flushes (every 50-100 items instead of per-item).
- Optional: skip cross-reference building for same-source benchmark entries.

### 5.5 Cosmetic (`collection/differ.py`)

- Detect XML content in `clean_html()` and use appropriate parser.

### 5.6 Configuration and Documentation

- OpenAI blocked pages: annotate in `sources.toml` as expected.
- Semantic Scholar API key: document setup in README Configuration table.
- Optional: OpenAI API endpoint for model catalog collection.

---

## 6. Verification Criteria

### Quality Filter (Issues 3, 5, 7)

- `ai-benchmark collect --source "Hugging Face Papers"` → items_extracted > 0 for both pages.
- `ai-benchmark collect --source "arXiv / Cornell"` → all three pages (cs.AI, cs.CL, cs.LG) produce items.
- `ai-benchmark collect --source "Hugging Face Forums"` → items appear in `ai-benchmark status`.
- `ai-benchmark status` → Papers count increases after collection.
- `pytest tests/ -k quality_filter` → no regressions.

### Date Parsing (Issue 5)

- `extract_date("2026-03-29T15:00:00.000Z")` returns `"2026-03-29"`.
- `extract_date("2026-03-29")` still returns `"2026-03-29"` (existing behavior preserved).
- `extract_date("March 29, 2026")` still returns `"2026-03-29"` (existing behavior preserved).

### Collectors (Issues 4, 6)

- `ai-benchmark collect --source "Hugging Face"` → items_extracted > 0 for leaderboard docs page.
- `ai-benchmark collect --source TechCrunch` → RSS produces items even with malformed XML (test with BOM-prefixed content).

### External Access (Issues 1, 2)

- Semantic Scholar: `ai-benchmark collect --source "Ai2"` → at least 5 papers returned with inter-query delays.
- OpenAI: collection log clearly marks 403 pages as expected/known.

### Performance (Issue 8)

- `ai-benchmark collect --source LMArena` → wall-clock time under 3 minutes (current: 6-10 min).
- Event count unchanged (no items lost from batch dedup).

### Regression

- `pytest` → all tests pass.
- `ruff check ai_benchmark/ tests/` → clean.
- `ruff format --check ai_benchmark/ tests/` → clean.
- Full collection run produces no new errors vs. 2026-03-30 baseline.
