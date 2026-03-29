"""Async HTTP fetcher with retry, concurrency control, and error handling."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, UTC

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class FetchResult:
    """Result of a single HTTP fetch."""

    url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body_text: str = ""
    elapsed_ms: float = 0.0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400 and self.error is None


class Fetcher:
    """Async HTTP fetcher with retry, backoff, concurrency control, and proxy support."""

    def __init__(
        self,
        user_agent: str = "ai-benchmark-pipeline/0.1",
        timeout: int = 30,
        max_concurrency: int = 5,
        retry_attempts: int = 3,
        retry_backoff_base: float = 2.0,
        proxy_url: str | None = None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff_base = retry_backoff_base
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client_kwargs: dict = {
            "timeout": httpx.Timeout(timeout),
            "follow_redirects": True,
            "http2": True,
            "headers": {"User-Agent": user_agent},
        }
        if proxy_url:
            self._client_kwargs["proxy"] = proxy_url

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL with retry and concurrency control."""
        async with self._semaphore:
            return await self._fetch_with_retry(url)

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """Fetch multiple URLs concurrently."""
        return await asyncio.gather(*(self.fetch(url) for url in urls))

    async def _fetch_with_retry(self, url: str) -> FetchResult:
        last_error: str | None = None
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(**self._client_kwargs) as client:
                    start = time.monotonic()
                    response = await client.get(url)
                    elapsed_ms = (time.monotonic() - start) * 1000

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        logger.warning(
                            "rate_limited",
                            url=url,
                            retry_after=retry_after,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 403:
                        logger.warning("access_forbidden", url=url)
                        return FetchResult(
                            url=url,
                            status_code=403,
                            headers=dict(response.headers),
                            elapsed_ms=elapsed_ms,
                            error="403 Forbidden",
                        )

                    return FetchResult(
                        url=url,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body_text=response.text,
                        elapsed_ms=elapsed_ms,
                    )

            except httpx.TimeoutException:
                last_error = f"Timeout after {self.timeout}s"
                logger.warning("fetch_timeout", url=url, attempt=attempt + 1)
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning("fetch_connect_error", url=url, attempt=attempt + 1, error=str(e))
            except httpx.HTTPError as e:
                last_error = f"HTTP error: {e}"
                logger.warning("fetch_error", url=url, attempt=attempt + 1, error=str(e))

            if attempt < self.retry_attempts - 1:
                backoff = self.retry_backoff_base ** attempt
                await asyncio.sleep(backoff)

        return FetchResult(
            url=url,
            status_code=0,
            error=last_error or "Unknown error after retries",
        )
