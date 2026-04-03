"""Tests for the coordination worker: fetch_and_extract() and worker_loop()."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_benchmark.coordination.types import FetchTask
from ai_benchmark.coordination.worker import fetch_and_extract, worker_loop
from ai_benchmark.sources.base import RawItem


def _make_task(**overrides) -> FetchTask:
    defaults = {
        "task_id": "test-task-1",
        "organization": "OpenAI",
        "page_url": "https://openai.com/pricing",
        "page_type": "pricing",
        "page_id": 42,
        "source_id": 1,
        "classification": "primary",
        "collector_class_name": "OpenAI",
    }
    defaults.update(overrides)
    return FetchTask(**defaults)


@dataclass
class MockFetchResult:
    url: str = "https://openai.com/pricing"
    status_code: int = 200
    headers: dict = field(default_factory=dict)
    body_text: str = "<html><body>Test</body></html>"
    elapsed_ms: float = 100.0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400 and self.error is None


def _make_settings():
    """Create a mock PipelineSettings."""
    settings = MagicMock()
    settings.github_token = None
    settings.semantic_scholar_api_key = None
    settings.max_concurrency = 5
    settings.retry_attempts = 3
    return settings


class TestFetchAndExtractStandardHTML:
    @pytest.mark.asyncio
    async def test_success_extracts_items(self):
        fetcher = AsyncMock()
        fetcher.fetch = AsyncMock(return_value=MockFetchResult())
        settings = _make_settings()
        task = _make_task()

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = [MagicMock(page_type="pricing", canonical_url="x")]
        mock_collector.extract_items.return_value = [
            RawItem(title="GPT-5 pricing update", url="https://openai.com/pricing"),
        ]

        with patch("ai_benchmark.coordination.worker.get_collector", return_value=mock_collector):
            result = await fetch_and_extract(task, fetcher, settings)

        assert result.task_id == "test-task-1"
        assert len(result.items) == 1
        assert result.items[0].title == "GPT-5 pricing update"
        assert result.html_content == "<html><body>Test</body></html>"
        assert result.fetch_error is None
        assert result.has_custom_collect is False
        assert result.fetch_status == 200

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_error(self):
        fetcher = AsyncMock()
        fetcher.fetch = AsyncMock(
            return_value=MockFetchResult(status_code=500, error="Internal Server Error")
        )
        settings = _make_settings()
        task = _make_task()

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = [MagicMock(page_type="pricing", canonical_url="x")]

        with patch("ai_benchmark.coordination.worker.get_collector", return_value=mock_collector):
            result = await fetch_and_extract(task, fetcher, settings)

        assert result.fetch_error == "Internal Server Error"
        assert result.items == []
        assert result.fetch_status == 500
        assert result.has_custom_collect is False


class TestFetchAndExtractAPICollector:
    @pytest.mark.asyncio
    async def test_api_collector_calls_collect_page(self):
        fetcher = AsyncMock()
        settings = _make_settings()
        task = _make_task(
            organization="Ai2",
            page_type="api",
            collector_class_name="Ai2",
        )

        mock_collector = MagicMock()
        mock_collector._API_PAGE_TYPES = {"api"}
        mock_collector.get_pages.return_value = [MagicMock(page_type="api", canonical_url="x")]
        mock_collector.collect_page = AsyncMock(
            return_value=([RawItem(title="Paper about LLMs")], None)
        )

        with patch("ai_benchmark.coordination.worker.get_collector", return_value=mock_collector):
            result = await fetch_and_extract(task, fetcher, settings)

        assert result.has_custom_collect is True
        assert result.html_content == ""
        assert len(result.items) == 1
        assert result.items[0].title == "Paper about LLMs"
        assert result.fetch_error is None
        # Fetcher.fetch should NOT have been called for API collectors
        fetcher.fetch.assert_not_called()


class TestFetchAndExtractRSSBackfill:
    @pytest.mark.asyncio
    async def test_rss_backfill_combines_items(self):
        fetcher = AsyncMock()
        fetcher.fetch = AsyncMock(return_value=MockFetchResult())
        settings = _make_settings()
        task = _make_task(
            page_url="https://news.google.com/rss/search?q=openai",
            page_type="rss",
            since_date=date(2026, 1, 1),
        )

        backfill_item = RawItem(title="Old OpenAI news", url="https://example.com/old")
        normal_item = RawItem(title="Current OpenAI news", url="https://example.com/new")

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = [
            MagicMock(page_type="rss", canonical_url="https://news.google.com/rss/search?q=openai")
        ]
        mock_collector.extract_items.return_value = [normal_item]
        mock_collector._enrich_rss_items = AsyncMock()
        mock_collector.collect_rss_backfill = AsyncMock(return_value=[backfill_item])

        with patch("ai_benchmark.coordination.worker.get_collector", return_value=mock_collector):
            result = await fetch_and_extract(task, fetcher, settings)

        assert len(result.items) == 2
        assert result.items[0].title == "Old OpenAI news"
        assert result.items[1].title == "Current OpenAI news"
        assert result.has_custom_collect is False


class TestWorkerLoop:
    @pytest.mark.asyncio
    async def test_exits_on_none_sentinel(self):
        task_queue: asyncio.Queue = asyncio.Queue()
        result_queue: asyncio.Queue = asyncio.Queue()
        fetcher = AsyncMock()
        settings = _make_settings()

        await task_queue.put(None)
        await worker_loop(0, task_queue, result_queue, fetcher, settings)

        assert result_queue.empty()

    @pytest.mark.asyncio
    async def test_processes_task_then_exits(self):
        task_queue: asyncio.Queue = asyncio.Queue()
        result_queue: asyncio.Queue = asyncio.Queue()
        fetcher = AsyncMock()
        fetcher.fetch = AsyncMock(return_value=MockFetchResult())
        settings = _make_settings()

        task = _make_task()
        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = [MagicMock(page_type="pricing", canonical_url="x")]
        mock_collector.extract_items.return_value = [RawItem(title="Test item")]

        await task_queue.put(task)
        await task_queue.put(None)  # sentinel

        with patch("ai_benchmark.coordination.worker.get_collector", return_value=mock_collector):
            await worker_loop(0, task_queue, result_queue, fetcher, settings)

        assert result_queue.qsize() == 1
        result = await result_queue.get()
        assert result.task_id == "test-task-1"
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_exception_produces_error_result(self):
        task_queue: asyncio.Queue = asyncio.Queue()
        result_queue: asyncio.Queue = asyncio.Queue()
        fetcher = AsyncMock()
        settings = _make_settings()

        task = _make_task()
        await task_queue.put(task)
        await task_queue.put(None)

        with patch(
            "ai_benchmark.coordination.worker.fetch_and_extract",
            side_effect=RuntimeError("boom"),
        ):
            await worker_loop(0, task_queue, result_queue, fetcher, settings)

        assert result_queue.qsize() == 1
        result = await result_queue.get()
        assert "boom" in result.fetch_error
        assert result.items == []
