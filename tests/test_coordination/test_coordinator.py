"""Tests for CollectionCoordinator — result processing, retry, and queue mechanics."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_benchmark.collection.differ import DiffResult
from ai_benchmark.coordination.coordinator import CollectionCoordinator
from ai_benchmark.coordination.types import CoordFetchResult, FetchTask
from ai_benchmark.sources.base import RawItem


def _make_settings(**overrides):
    """Create a mock PipelineSettings."""
    settings = MagicMock()
    settings.database_url = "sqlite+aiosqlite://"
    settings.user_agent = "test/1.0"
    settings.request_timeout = 10
    settings.max_concurrency = 2
    settings.retry_attempts = 3
    settings.retry_backoff_base = 1.0
    settings.proxy_url = None
    settings.github_token = None
    settings.semantic_scholar_api_key = None
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _make_result(**overrides) -> CoordFetchResult:
    defaults = {
        "task_id": "result-1",
        "organization": "OpenAI",
        "page_url": "https://openai.com/pricing",
        "page_type": "pricing",
        "page_id": 42,
        "source_id": 1,
        "classification": "primary",
        "items": [RawItem(title="GPT-5 pricing update", url="https://openai.com/pricing")],
        "html_content": "<html><body>Test</body></html>",
        "fetch_status": 200,
        "fetch_error": None,
        "elapsed_ms": 100.0,
        "fetched_at": datetime.now(UTC),
        "css_selectors": {},
        "has_custom_collect": False,
        "since_date": None,
        "priority": False,
        "attempt": 0,
    }
    defaults.update(overrides)
    return CoordFetchResult(**defaults)


def _make_task(**overrides) -> FetchTask:
    defaults = {
        "task_id": "task-1",
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


class TestProcessResultSuccess:
    """_process_result success path: snapshot compare → process_items → health update."""

    @pytest.mark.asyncio
    async def test_success_calls_snapshot_and_process_items(self):
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        result = _make_result()

        # Mock session factory
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        # Mock Page query for _update_health
        mock_page = MagicMock()
        mock_page.consecutive_failures = 2
        mock_page.times_polled = 5
        mock_page.last_polled_at = None
        mock_page.last_changed_at = None
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        mock_diff = DiffResult(changed=True, added_lines=["new line"], change_ratio=0.5)
        mock_snapshot = MagicMock()
        mock_events = [MagicMock()]

        with (
            patch("ai_benchmark.coordination.coordinator.SnapshotManager") as mock_snap_mgr,
            patch(
                "ai_benchmark.coordination.coordinator.process_items",
                new_callable=AsyncMock,
                return_value=mock_events,
            ),
        ):
            mock_snap_mgr.return_value.compare_with_latest = AsyncMock(
                return_value=(mock_diff, mock_snapshot)
            )

            retry = await coord._process_result(result, stats)

        assert retry is None
        assert stats["tasks_completed"] == 1
        assert stats["items_processed"] == 1
        assert stats["events_created"] == 1
        # Health should be reset
        assert mock_page.consecutive_failures == 0
        assert mock_page.times_polled == 6

    @pytest.mark.asyncio
    async def test_custom_collector_skips_snapshot(self):
        """has_custom_collect=True → skips SnapshotManager entirely."""
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        result = _make_result(has_custom_collect=True, html_content="")
        mock_events = [MagicMock()]

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        mock_page = MagicMock()
        mock_page.consecutive_failures = 0
        mock_page.times_polled = 3
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        with (
            patch("ai_benchmark.coordination.coordinator.SnapshotManager") as mock_snap_mgr,
            patch(
                "ai_benchmark.coordination.coordinator.process_items",
                new_callable=AsyncMock,
                return_value=mock_events,
            ),
        ):
            retry = await coord._process_result(result, stats)

            # SnapshotManager should NOT have been instantiated or called
            mock_snap_mgr.assert_not_called()

        assert retry is None
        assert stats["tasks_completed"] == 1
        assert stats["items_processed"] == 1


class TestProcessResultFailure:
    """_process_result failure + retry path."""

    @pytest.mark.asyncio
    async def test_failure_increments_consecutive_failures(self):
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        result = _make_result(
            fetch_error="Connection timeout",
            items=[],
            fetch_status=0,
            attempt=0,
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        mock_page = MagicMock()
        mock_page.consecutive_failures = 1
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        retry = await coord._process_result(result, stats)

        assert stats["tasks_failed"] == 1
        assert mock_page.consecutive_failures == 2
        # Should produce a retry task (attempt 0 < retry_attempts - 1 = 2)
        assert retry is not None
        assert retry.attempt == 1
        assert retry.organization == "OpenAI"
        assert retry.task_id != result.task_id  # new task_id

    @pytest.mark.asyncio
    async def test_failure_no_retry_on_last_attempt(self):
        settings = _make_settings(retry_attempts=3)
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        result = _make_result(
            fetch_error="Server error",
            items=[],
            fetch_status=500,
            attempt=2,  # attempt == retry_attempts - 1
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        mock_page = MagicMock()
        mock_page.consecutive_failures = 4
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        retry = await coord._process_result(result, stats)

        assert retry is None
        assert stats["tasks_failed"] == 1


class TestProcessResultUnchanged:
    """_process_result with no changes detected → skip processing."""

    @pytest.mark.asyncio
    async def test_unchanged_skips_processing(self):
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        result = _make_result(since_date=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        mock_page = MagicMock()
        mock_page.consecutive_failures = 0
        mock_page.times_polled = 10
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        no_change_diff = DiffResult(changed=False)
        mock_snapshot = MagicMock()

        with (
            patch("ai_benchmark.coordination.coordinator.SnapshotManager") as mock_snap_mgr,
            patch(
                "ai_benchmark.coordination.coordinator.process_items",
                new_callable=AsyncMock,
            ) as mock_proc,
        ):
            mock_snap_mgr.return_value.compare_with_latest = AsyncMock(
                return_value=(no_change_diff, mock_snapshot)
            )

            retry = await coord._process_result(result, stats)

        assert retry is None
        assert stats["tasks_completed"] == 1
        assert stats["items_processed"] == 0
        # process_items should NOT have been called
        mock_proc.assert_not_called()


class TestProcessResultDateFilter:
    """Backfill mode: since_date filters items."""

    @pytest.mark.asyncio
    async def test_date_filter_applied_on_backfill(self):
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        stats = {
            "tasks_created": 1,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        old_item = RawItem(title="Old item", date_text="2020-01-01")
        new_item = RawItem(title="New item", date_text="2026-03-01")

        result = _make_result(
            items=[old_item, new_item],
            since_date=date(2026, 1, 1),
            has_custom_collect=True,  # skip snapshot check
            html_content="",
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        coord._session_factory = MagicMock(return_value=mock_session)

        mock_page = MagicMock()
        mock_page.consecutive_failures = 0
        mock_page.times_polled = 0
        mock_page_result = MagicMock()
        mock_page_result.scalar_one_or_none.return_value = mock_page
        mock_session.execute = AsyncMock(return_value=mock_page_result)

        with patch(
            "ai_benchmark.coordination.coordinator.process_items",
            new_callable=AsyncMock,
            return_value=[MagicMock()],
        ) as mock_proc:
            retry = await coord._process_result(result, stats)

        assert retry is None
        # process_items should have been called with filtered items
        call_args = mock_proc.call_args
        processed_items = call_args[0][1]  # 2nd positional arg
        # Only the new item should pass the date filter
        assert len(processed_items) == 1
        assert processed_items[0].title == "New item"


class TestCollectAllEndToEnd:
    """collect_all with mocked workers — end-to-end queue mechanics."""

    @pytest.mark.asyncio
    async def test_collect_all_with_mocked_tasks(self):
        settings = _make_settings(max_concurrency=2)
        coord = CollectionCoordinator(settings)

        tasks = [
            _make_task(task_id="t1", page_url="https://openai.com/page1"),
            _make_task(task_id="t2", page_url="https://openai.com/page2"),
        ]

        # Mock _create_tasks to return our tasks
        coord._create_tasks = AsyncMock(return_value=tasks)

        # Mock _process_result to always succeed
        coord._process_result = AsyncMock(return_value=None)

        # Mock session factory for setup/shutdown
        coord._session_factory = MagicMock()
        coord._fetcher = AsyncMock()

        # Mock worker_loop to just consume tasks and produce results
        async def fake_worker(wid, tq, rq, fetcher, settings):
            while True:
                task = await tq.get()
                if task is None:
                    return
                await rq.put(_make_result(task_id=task.task_id))

        with patch(
            "ai_benchmark.coordination.coordinator.worker_loop",
            side_effect=fake_worker,
        ):
            stats = await coord.collect_all()

        assert stats["tasks_created"] == 2
        # _process_result called once per task
        assert coord._process_result.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_all_empty_returns_immediately(self):
        settings = _make_settings()
        coord = CollectionCoordinator(settings)
        coord._create_tasks = AsyncMock(return_value=[])
        coord._session_factory = MagicMock()
        coord._fetcher = AsyncMock()

        stats = await coord.collect_all()

        assert stats["tasks_created"] == 0
        assert stats["tasks_completed"] == 0

    @pytest.mark.asyncio
    async def test_collect_all_with_retry(self):
        """Result that triggers retry increases pending count."""
        settings = _make_settings(max_concurrency=1, retry_attempts=3)
        coord = CollectionCoordinator(settings)

        tasks = [_make_task(task_id="t1")]
        coord._create_tasks = AsyncMock(return_value=tasks)
        coord._session_factory = MagicMock()
        coord._fetcher = AsyncMock()

        call_count = 0

        async def mock_process_result(result, stats):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return a retry task
                return _make_task(task_id="retry-t1", attempt=1)
            # Second call: success
            stats["tasks_completed"] += 1
            return None

        coord._process_result = AsyncMock(side_effect=mock_process_result)

        async def fake_worker(wid, tq, rq, fetcher, settings):
            while True:
                task = await tq.get()
                if task is None:
                    return
                await rq.put(_make_result(task_id=task.task_id))

        with patch(
            "ai_benchmark.coordination.coordinator.worker_loop",
            side_effect=fake_worker,
        ):
            stats = await coord.collect_all()

        assert stats["tasks_created"] == 1
        # _process_result called twice: original + retry
        assert call_count == 2


class TestQueueBackpressure:
    """Bounded queue prevents unbounded memory growth."""

    @pytest.mark.asyncio
    async def test_bounded_queue_blocks_producer(self):
        """With maxsize=2, putting 3 items blocks until consumer reads."""
        queue: asyncio.Queue[int] = asyncio.Queue(maxsize=2)

        await queue.put(1)
        await queue.put(2)

        # Queue is now full — put should not complete immediately
        put_done = False

        async def delayed_put():
            nonlocal put_done
            await queue.put(3)
            put_done = True

        producer = asyncio.create_task(delayed_put())
        # Give the event loop a tick — producer should still be blocked
        await asyncio.sleep(0)
        assert not put_done

        # Consume one item — producer should unblock
        await queue.get()
        await asyncio.sleep(0)
        await producer
        assert put_done
