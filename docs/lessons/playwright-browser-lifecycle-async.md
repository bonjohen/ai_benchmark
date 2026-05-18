# Playwright Browser Lifecycle in Async Pipelines

## The Lesson

Shared browser instances in async code need explicit synchronization at creation time and explicit cleanup at shutdown. Without both, you get leaked browser processes from races and resource warnings from incomplete teardown — problems that surface only under concurrent load, not in unit tests.

## Context

A data collection pipeline fetches ~80 pages from AI vendor websites. Six pages were blocked by Cloudflare JS challenges, returning empty or challenge HTML instead of real content. Playwright (headless Chromium) was added as a fetcher option for these pages, with a `browser=true` flag per page in the source catalog. The fetcher used a singleton browser instance shared across concurrent page fetches within a collection run.

## What Happened

1. A `PlaywrightFetcher` class was implemented with a lazy `_ensure_browser()` method that checked `self._browser is None` and launched Chromium if needed. Worked perfectly in serial tests.
2. In production, the collection coordinator dispatched multiple Playwright-flagged pages concurrently. Multiple async workers hit `_ensure_browser()` simultaneously, all saw `_browser=None`, and each launched a separate Chromium instance.
3. Only the last instance was assigned to `self._browser`. The others became orphaned processes — still running, consuming memory, but unreachable for cleanup.
4. The fix was an `asyncio.Lock` with double-checked locking: acquire the lock, check again if the browser exists, only then launch. This guaranteed exactly one browser instance.
5. Shutdown on Windows produced `ResourceWarning` for unclosed transports. Playwright's `stop()` method is synchronous but the underlying transport cleanup is async. A 250ms grace period after `stop()` plus suppressed warnings during GC resolved the issue.
6. The Windows-specific timing sensitivity (Python 3.14 transport cleanup) would not have been caught on Linux CI.

## Key Insights

- **Lazy singletons in async code need a lock.** The classic `if instance is None: create()` pattern is a race condition when multiple coroutines can execute it concurrently. An `asyncio.Lock` is the minimal correct fix.
- **Double-checked locking matters for performance.** Check without lock first (fast path for the common case where the browser already exists), then acquire lock and check again (correctness for the creation race). Without the outer check, every page fetch pays the lock acquisition cost.
- **Browser cleanup is platform-dependent.** Playwright's Python bindings abstract away platform differences for page operations but not for process lifecycle. Windows transport cleanup timing differs from Linux, and tests that pass on one platform may leak resources on the other.
- **Leaked processes are silent failures.** Unlike exceptions, orphaned browser processes don't crash the pipeline — they just consume resources until the OS or GC cleans them up. Monitoring process count or memory usage during collection runs is the only way to catch this class of bug.
- **Graceful fallback preserves pipeline reliability.** Pages flagged for Playwright fall back to httpx if Playwright fails. This means a browser crash doesn't block collection — the page gets a lower-quality fetch attempt rather than no attempt.

## Examples

**Race condition (before fix):**
```python
async def _ensure_browser(self):
    if self._browser is None:          # Multiple coroutines pass this check
        pw = await async_playwright()   # Each launches a browser
        self._browser = await pw.chromium.launch()  # Last one wins
```

**Double-checked locking (after fix):**
```python
async def _ensure_browser(self):
    if self._browser is not None:      # Fast path, no lock needed
        return
    async with self._lock:             # Serialize creation
        if self._browser is not None:  # Re-check after acquiring lock
            return
        pw = await async_playwright()
        self._browser = await pw.chromium.launch()
```

## Applicability

Applies to any async system that manages a shared expensive resource (browser, database connection pool, gRPC channel, ML model). Does NOT apply to resources that are cheap to create per-request — connection pooling overhead only pays off when creation cost is high (Chromium launch: ~1-2 seconds).

## Related Lessons

- [RSS as Fallback Collection Method](rss-fallback-collection-method.md) — The alternative approach for Cloudflare-blocked sites that doesn't require a browser at all.
