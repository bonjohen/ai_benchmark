"""Tests for the path pattern prober."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ai_benchmark.collection.fetcher import FetchResult
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.processing.path_prober import discover_new_paths, probe_domain


@pytest.mark.asyncio
async def test_probe_domain_returns_200s():
    """probe_domain returns paths that return HTTP 200."""
    fetcher = AsyncMock()

    # Simulate some 200s and some 404s
    async def mock_fetch(url, **kwargs):
        if "/pricing" in url or "/blog" in url:
            return FetchResult(url=url, status_code=200, body_text="OK")
        return FetchResult(url=url, status_code=404, body_text="", error="Not Found")

    fetcher.fetch = mock_fetch
    paths = await probe_domain("example.com", fetcher)
    assert "/pricing" in paths
    assert "/blog" in paths
    assert "/changelog" not in paths


@pytest.mark.asyncio
async def test_probe_domain_handles_errors():
    """probe_domain handles connection errors gracefully."""
    fetcher = AsyncMock()
    fetcher.fetch.side_effect = Exception("Connection error")
    paths = await probe_domain("example.com", fetcher)
    assert paths == []


@pytest.mark.asyncio
async def test_discover_new_paths_returns_unconfigured(db_session):
    """discover_new_paths returns only paths not already configured."""
    source = Source(
        source_name="Test",
        category="test",
        organization="Test",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=4.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.flush()

    # Configure /pricing but not /blog
    page = Page(
        source_id=source.id,
        canonical_url="https://example.com/pricing",
        page_type="pricing",
    )
    db_session.add(page)
    await db_session.flush()

    # Mock fetcher that finds both /pricing and /blog
    async def mock_fetch(url, **kwargs):
        if "/pricing" in url or "/blog" in url:
            return FetchResult(url=url, status_code=200, body_text="OK")
        return FetchResult(url=url, status_code=404, body_text="", error="Not Found")

    fetcher = AsyncMock()
    fetcher.fetch = mock_fetch

    new_paths = await discover_new_paths(db_session, fetcher)
    paths = [p for _, p in new_paths]

    # /blog is new, /pricing is already configured
    assert "/blog" in paths
    assert "/pricing" not in paths
