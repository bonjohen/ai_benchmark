"""Base API client for JSON REST sources (GitHub, Semantic Scholar, HF)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class APIClient:
    """Base async API client with auth, rate limiting, and pagination support.

    Subclass and override `base_url`, `auth_header()`, and `parse_response()`
    for specific APIs.
    """

    base_url: str = ""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        max_concurrency: int = 5,
    ):
        self.api_key = api_key
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def auth_header(self) -> dict[str, str]:
        """Return authorization headers. Override in subclasses."""
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Make an authenticated GET request with 429 retry support."""
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}" if self.base_url else path
        headers = {
            "Accept": "application/json",
            "User-Agent": "ai-benchmark-pipeline/0.1",
            **self.auth_header(),
        }
        async with self._semaphore, httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True
        ) as client:
            for attempt in range(max_retries):
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "30"))
                    logger.warning(
                        "api_rate_limited",
                        url=url,
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            # Final attempt exhausted — raise the last response's status
            response.raise_for_status()
            return response.json()  # unreachable, but satisfies type checker

    async def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_param: str = "page",
        per_page_param: str = "per_page",
        per_page: int = 100,
        max_pages: int = 10,
        results_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch paginated results up to max_pages."""
        all_results: list[dict[str, Any]] = []
        params = dict(params or {})
        params[per_page_param] = per_page

        for page_num in range(1, max_pages + 1):
            params[page_param] = page_num
            data = await self.get(path, params)

            if results_key:
                items = data.get(results_key, [])
            elif isinstance(data, list):
                items = data
            else:
                items = [data]

            all_results.extend(items)

            if len(items) < per_page:
                break

        return all_results
