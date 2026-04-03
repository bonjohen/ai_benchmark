"""Tests for the async HTTP fetcher."""

from __future__ import annotations

import httpx
import pytest
import respx

from ai_benchmark.collection.fetcher import Fetcher


@pytest.mark.asyncio
async def test_fetch_success():
    fetcher = Fetcher(retry_attempts=1)
    with respx.mock:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(200, text="<html>Hello</html>")
        )
        result = await fetcher.fetch("https://example.com/page")
    assert result.ok
    assert result.status_code == 200
    assert "Hello" in result.body_text


@pytest.mark.asyncio
async def test_fetch_403():
    fetcher = Fetcher(retry_attempts=1)
    with respx.mock:
        respx.get("https://example.com/blocked").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = await fetcher.fetch("https://example.com/blocked")
    assert not result.ok
    assert result.status_code == 403
    assert result.error == "403 Forbidden"


@pytest.mark.asyncio
async def test_fetch_retry_on_timeout():
    fetcher = Fetcher(timeout=1, retry_attempts=2, retry_backoff_base=0.01)
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(200, text="OK")

    with respx.mock:
        respx.get("https://example.com/slow").mock(side_effect=side_effect)
        result = await fetcher.fetch("https://example.com/slow")
    assert result.ok
    assert call_count == 2


@pytest.mark.asyncio
async def test_fetch_many():
    fetcher = Fetcher(retry_attempts=1)
    with respx.mock:
        respx.get("https://example.com/a").mock(return_value=httpx.Response(200, text="A"))
        respx.get("https://example.com/b").mock(return_value=httpx.Response(200, text="B"))
        results = await fetcher.fetch_many(["https://example.com/a", "https://example.com/b"])
    assert len(results) == 2
    assert all(r.ok for r in results)


@pytest.mark.asyncio
async def test_fetch_success_logs_fetch_complete(capture_logs):
    fetcher = Fetcher(retry_attempts=1)
    with respx.mock:
        respx.get("https://example.com/ok").mock(return_value=httpx.Response(200, text="Hello"))
        await fetcher.fetch("https://example.com/ok")

    event_names = [entry["event"] for entry in capture_logs]
    assert "fetch_complete" in event_names
