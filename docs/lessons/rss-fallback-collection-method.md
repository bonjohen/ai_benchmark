# RSS as Fallback Collection Method

## The Lesson

When primary collection methods fail due to anti-bot defenses (Cloudflare, JS rendering), Google News RSS feeds provide a reliable fallback that requires no browser automation — but RSS item bodies are often useless title echoes that need enrichment from the actual article pages.

## Context

A pipeline monitors ~80 pages across AI vendor websites. Several high-value sources (Mistral, Cohere, OpenAI, xAI) use Cloudflare protection or heavy JavaScript rendering that defeats standard HTTP fetching. The pipeline needed signal from these sources without depending entirely on browser automation, which is heavyweight and fragile.

## What Happened

1. Standard httpx fetches of Cloudflare-protected pages returned challenge HTML or empty bodies. These pages produced zero events despite being high-priority sources.
2. Google News RSS feeds (`news.google.com/rss/search?q=site:example.com`) were added as an alternative collection method. RSS feeds bypass Cloudflare entirely because Google's crawler has already fetched and indexed the content.
3. RSS items arrived with useful titles and URLs but useless descriptions — Google News RSS bodies are typically just the title repeated, not article summaries.
4. An enrichment step was added: for each RSS item, follow the Google News redirect URL to the actual article page, extract `og:description` or `<meta name="description">` from the HTML, and replace the title-echo body with real content. Rate-limited at 1 request per second to avoid hammering source sites.
5. The enrichment worked in the main collection path but was bypassed by the coordinator worker path, which called `extract_items()` directly. A second integration point was added to ensure enrichment applied regardless of entry path.
6. The result: sources that were previously zero-yield now produce events reliably through RSS, with article-quality descriptions rather than title echoes.

## Key Insights

- **RSS bypasses anti-bot defenses by design.** Google's crawler has already done the hard work of rendering JavaScript and solving challenges. RSS feeds are a free, stable proxy for content that's hostile to direct fetching.
- **RSS metadata quality varies wildly.** Some feeds have full article summaries; Google News RSS specifically echoes titles as descriptions. Always check what the feed actually provides before assuming the data is usable.
- **Enrichment is a separate concern from collection.** Collecting the RSS item and enriching it with real page metadata are independent operations. Separating them means a failed enrichment doesn't block collection — you still get the title and URL.
- **Multiple code paths need the same enrichment.** When a processing step is added to one code path (e.g., `collect_page`), check whether other paths (e.g., coordinator worker) bypass it. Integration-level wiring bugs are easy to miss because each path works correctly in isolation.
- **Rate limiting enrichment is non-negotiable.** Following RSS links to source pages is effectively crawling those sites. Without rate limiting, enrichment can trigger the same anti-bot defenses you're trying to avoid.

## Applicability

Applies to any monitoring system that needs to track changes on websites with anti-bot protection, paywalls, or heavy JavaScript rendering. Also applies to news aggregation, competitive intelligence, and content monitoring. Does NOT apply when you need full page HTML (e.g., for HTML diffing or snapshot comparison) — RSS gives you metadata, not page structure.

## Related Lessons

- [Playwright Browser Lifecycle in Async Pipelines](playwright-browser-lifecycle-async.md) — The browser-based alternative for when RSS doesn't provide enough signal and full page rendering is needed.
