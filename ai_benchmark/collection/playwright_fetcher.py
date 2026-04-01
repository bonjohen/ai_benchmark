"""Playwright-based fetcher for Cloudflare-protected pages.

Uses headless Chromium to solve JS challenges. Only used for pages
marked with ``browser = true`` in sources.toml. Falls back gracefully
if playwright is not installed.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .fetcher import FetchResult

logger = structlog.get_logger(__name__)

# Sentinel for import availability
_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def is_playwright_available() -> bool:
    """Check if playwright is installed."""
    return _PLAYWRIGHT_AVAILABLE


class PlaywrightFetcher:
    """Headless Chromium fetcher that solves Cloudflare challenges.

    Reuses a single browser instance across fetches. Call ``aclose()``
    when done to shut down the browser.
    """

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self._playwright = None
        self._browser = None
        self._launch_lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Launch browser on first use (serialized to prevent duplicate launches)."""
        if self._browser is None:
            async with self._launch_lock:
                if self._browser is None:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(headless=True)
                    logger.info("playwright_browser_launched")
        return self._browser

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL using headless Chromium.

        Waits for the Cloudflare challenge to resolve by watching for
        the page to reach a non-challenge state (networkidle or body content).
        """
        from datetime import UTC, datetime

        from .fetcher import FetchResult

        start = asyncio.get_event_loop().time()
        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            # Wait for Cloudflare challenge to resolve. networkidle may not
            # fire if the page has long-polling — suppress the timeout.
            import contextlib

            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=15000)

            # If still on challenge page, wait a bit more for JS execution
            content = await page.content()
            if len(content) < 1000 or "challenge" in content[:500].lower():
                await asyncio.sleep(3)
                content = await page.content()

            status = response.status if response else 0
            elapsed = (asyncio.get_event_loop().time() - start) * 1000

            await context.close()

            logger.info(
                "playwright_fetch_complete",
                url=url,
                status=status,
                content_length=len(content),
                elapsed_ms=round(elapsed),
            )

            return FetchResult(
                url=url,
                status_code=status,
                body_text=content,
                elapsed_ms=elapsed,
                fetched_at=datetime.now(UTC),
            )

        except Exception as e:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            logger.warning("playwright_fetch_error", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                elapsed_ms=elapsed,
                error=f"Playwright error: {e}",
            )

    async def aclose(self) -> None:
        """Shut down the browser and playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            # Force GC while the event loop is still active so Playwright's
            # subprocess transports finalize now (with warnings suppressed)
            # instead of during interpreter shutdown where they produce
            # ResourceWarning spam on Python 3.14 + Windows.
            import gc
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning)
                gc.collect()
            logger.info("playwright_browser_closed")
