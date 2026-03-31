"""CollectionCoordinator — single-writer orchestrator for the collection pipeline."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from ..collection.fetcher import Fetcher
from ..collection.snapshot import SnapshotManager
from ..config.settings import PipelineSettings, load_source_catalog
from ..models.base import create_engine, create_session_factory
from ..processing.pipeline import process_items
from .types import CoordFetchResult, FetchTask
from .worker import worker_loop

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class CollectionCoordinator:
    """Centralized coordinator: creates tasks, dispatches to workers, processes results.

    All database access is confined to this class. Workers perform only
    HTTP fetching and HTML extraction with no DB access.
    """

    def __init__(self, settings: PipelineSettings) -> None:
        self._settings = settings
        self._engine = None
        self._session_factory = None
        self._fetcher: Fetcher | None = None
        self._worker_count = settings.max_concurrency

    async def setup(self) -> None:
        """Create async engine, session factory, and Fetcher."""
        self._engine = create_engine(self._settings.database_url)
        self._session_factory = create_session_factory(self._engine)
        self._fetcher = Fetcher(
            user_agent=self._settings.user_agent,
            timeout=self._settings.request_timeout,
            max_concurrency=self._settings.max_concurrency,
            retry_attempts=self._settings.retry_attempts,
            retry_backoff_base=self._settings.retry_backoff_base,
            proxy_url=self._settings.proxy_url,
        )

    async def shutdown(self) -> None:
        """Close Fetcher and dispose engine."""
        if self._fetcher:
            await self._fetcher.aclose()
        if self._engine:
            await self._engine.dispose()

    async def collect_all(
        self,
        organizations: list[str] | None = None,
        since_date: Any | None = None,
    ) -> dict[str, int]:
        """Main entry point. Coordinate workers to fetch all pages, process results.

        Returns stats dict: tasks_created, tasks_completed, tasks_failed,
        items_processed, events_created.
        """
        stats: dict[str, int] = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "items_processed": 0,
            "events_created": 0,
        }

        tasks = await self._create_tasks(organizations, since_date)
        stats["tasks_created"] = len(tasks)

        if not tasks:
            return stats

        # Initialize bounded queues
        queue_size = 2 * self._worker_count
        task_queue: asyncio.Queue[FetchTask | None] = asyncio.Queue(maxsize=queue_size)
        result_queue: asyncio.Queue[CoordFetchResult] = asyncio.Queue(maxsize=queue_size)

        # Track pending tasks for completion detection
        pending = 0

        # Launch worker tasks
        worker_tasks = [
            asyncio.create_task(
                worker_loop(i, task_queue, result_queue, self._fetcher, self._settings)
            )
            for i in range(self._worker_count)
        ]

        async def _produce() -> None:
            """Enqueue all initial tasks (sentinels sent after retries complete)."""
            for task in tasks:
                await task_queue.put(task)

        # Run producer and consumer concurrently
        producer = asyncio.create_task(_produce())
        pending = len(tasks)

        while pending > 0:
            result = await result_queue.get()
            pending -= 1
            retry_task = await self._process_result(result, stats)
            if retry_task is not None:
                await task_queue.put(retry_task)
                pending += 1

        # All work done (including retries) — send shutdown sentinels
        for _ in range(self._worker_count):
            await task_queue.put(None)

        await producer
        await asyncio.gather(*worker_tasks)

        return stats

    async def _create_tasks(
        self,
        organizations: list[str] | None,
        since_date: Any | None,
    ) -> list[FetchTask]:
        """Load catalog, query DB for source/page IDs, build FetchTask per page."""
        from sqlalchemy import select

        from ..models.sources import Page as PageModel
        from ..models.sources import Source as SourceModel

        catalog = load_source_catalog()
        if organizations:
            org_set = set(organizations)
            catalog = [s for s in catalog if s.organization in org_set]

        tasks: list[FetchTask] = []

        async with self._session_factory() as session:
            for source_config in catalog:
                # Look up source in DB
                stmt = select(SourceModel).where(
                    SourceModel.organization == source_config.organization
                )
                result = await session.execute(stmt)
                source_record = result.scalar_one_or_none()

                if source_record is None:
                    source_record = SourceModel(
                        source_name=source_config.source_name,
                        category=source_config.category,
                        organization=source_config.organization,
                        homepage_url=source_config.homepage_url,
                        base_domain=source_config.base_domain,
                        trust_rating=source_config.trust_rating,
                        source_role=getattr(source_config, "source_role", "primary source"),
                        classification=source_config.classification,
                        collection_method=source_config.collection_method,
                    )
                    session.add(source_record)
                    await session.flush()

                source_id = source_record.id

                for page_config in source_config.pages:
                    # Look up or create Page record
                    page_stmt = select(PageModel).where(
                        PageModel.canonical_url == page_config.canonical_url
                    )
                    page_result = await session.execute(page_stmt)
                    page_record = page_result.scalar_one_or_none()

                    if page_record is None and source_id:
                        page_record = PageModel(
                            source_id=source_id,
                            canonical_url=page_config.canonical_url,
                            page_type=page_config.page_type,
                        )
                        session.add(page_record)
                        await session.flush()

                    page_id = page_record.id if page_record else None

                    tasks.append(
                        FetchTask(
                            task_id=uuid.uuid4().hex,
                            organization=source_config.organization,
                            page_url=page_config.canonical_url,
                            page_type=page_config.page_type,
                            page_id=page_id,
                            source_id=source_id,
                            classification=source_config.classification,
                            collector_class_name=source_config.organization,
                            css_selectors=page_config.css_selectors,
                            since_date=since_date,
                            priority=page_config.priority,
                        )
                    )

            await session.commit()

        return tasks

    async def _process_result(
        self,
        result: CoordFetchResult,
        stats: dict[str, int],
    ) -> FetchTask | None:
        """Process a single worker result. Returns a retry FetchTask or None."""
        log = logger.bind(
            organization=result.organization,
            url=result.page_url,
            task_id=result.task_id,
        )

        async with self._session_factory() as session:
            # Fetch error → retry (transient) or record failure (permanent)
            if result.fetch_error:
                await self._handle_failure(result, session, log)
                await session.commit()
                stats["tasks_failed"] += 1

                # Don't retry permanent failures (403 WAF, 404 not found)
                _permanent = {403, 404}
                if (
                    result.fetch_status not in _permanent
                    and result.attempt < self._settings.retry_attempts - 1
                ):
                    retry = FetchTask(
                        task_id=uuid.uuid4().hex,
                        organization=result.organization,
                        page_url=result.page_url,
                        page_type=result.page_type,
                        page_id=result.page_id,
                        source_id=result.source_id,
                        classification=result.classification,
                        collector_class_name=result.organization,
                        css_selectors=result.css_selectors,
                        since_date=result.since_date,
                        priority=result.priority,
                        attempt=result.attempt + 1,
                    )
                    log.info("retry_scheduled", attempt=retry.attempt)
                    return retry
                return None

            # Snapshot comparison for standard (non-API) collectors
            items = result.items
            if not result.has_custom_collect and result.page_id and result.html_content:
                snapshot_mgr = SnapshotManager(session)
                selectors = list(result.css_selectors.values()) if result.css_selectors else None
                diff, _snapshot = await snapshot_mgr.compare_with_latest(
                    result.page_id, result.html_content, selectors
                )

                if not diff.changed and not result.since_date:
                    log.debug("no_change")
                    await self._update_health(result, session, had_items=False)
                    await session.commit()
                    stats["tasks_completed"] += 1
                    return None

                # Quality filter (skip in backfill mode)
                if not result.since_date and items:
                    from ..config.settings import PageConfig
                    from ..processing.quality_filter import is_low_value_page

                    page_config = PageConfig(
                        canonical_url=result.page_url,
                        page_type=result.page_type,
                        css_selectors=result.css_selectors,
                    )
                    if is_low_value_page(diff, items, page_config):
                        log.debug("low_value_page_filtered", count=len(items))
                        await self._update_health(result, session, had_items=False)
                        await session.commit()
                        stats["tasks_completed"] += 1
                        return None

            # Date filter for backfill
            if result.since_date and items:
                from ..scheduling.scheduler import _item_in_date_range

                items = [item for item in items if _item_in_date_range(item, result.since_date)]

            # Process items
            if items:
                events = await process_items(
                    session,
                    items,
                    source_id=result.source_id,
                    page_id=result.page_id,
                    organization=result.organization,
                    source_type=result.classification,
                    classification=result.classification,
                )
                stats["items_processed"] += len(items)
                stats["events_created"] += len(events)

            await self._update_health(result, session, had_items=bool(items))
            await session.commit()
            stats["tasks_completed"] += 1
            log.info("result_processed", items=len(items))

        return None

    async def _handle_failure(
        self,
        result: CoordFetchResult,
        session: AsyncSession,
        log: Any,
    ) -> None:
        """Increment Page.consecutive_failures on fetch error."""
        if result.page_id:
            from sqlalchemy import select

            from ..models.sources import Page as PageModel

            stmt = select(PageModel).where(PageModel.id == result.page_id)
            page_result = await session.execute(stmt)
            page = page_result.scalar_one_or_none()
            if page:
                page.consecutive_failures = (page.consecutive_failures or 0) + 1

        log.warning(
            "fetch_error",
            error=result.fetch_error,
            attempt=result.attempt,
        )

    async def _update_health(
        self,
        result: CoordFetchResult,
        session: AsyncSession,
        had_items: bool,
    ) -> None:
        """Reset Page.consecutive_failures, update polling metadata."""
        if not result.page_id:
            return

        from sqlalchemy import select

        from ..models.sources import Page as PageModel

        stmt = select(PageModel).where(PageModel.id == result.page_id)
        page_result = await session.execute(stmt)
        page = page_result.scalar_one_or_none()
        if page:
            page.consecutive_failures = 0
            page.times_polled = (page.times_polled or 0) + 1
            page.last_polled_at = datetime.now(UTC)
            if had_items:
                page.last_changed_at = datetime.now(UTC)
