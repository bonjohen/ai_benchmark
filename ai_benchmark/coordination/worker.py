"""Worker logic for the collection coordinator — fetch and extract without DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from ..config.settings import PageConfig, SourceConfig
from ..sources.registry import get_collector
from .types import CoordFetchResult, FetchTask

if TYPE_CHECKING:
    import asyncio

    from ..collection.fetcher import Fetcher
    from ..config.settings import PipelineSettings

logger = structlog.get_logger(__name__)


async def fetch_and_extract(
    task: FetchTask,
    fetcher: Fetcher,
    settings: PipelineSettings,
) -> CoordFetchResult:
    """Fetch a page and extract items. No database access.

    Three paths:
    1. API collector: delegate to collector.collect_page() which handles its own fetch.
    2. Standard HTML: fetch via Fetcher, then collector.extract_items().
    3. RSS backfill: if since_date set and page is Google News RSS, also run
       collect_rss_backfill() for historical date windows.
    """
    start = datetime.now(UTC)

    # Build minimal SourceConfig for the collector
    source_config = SourceConfig(
        source_name=task.organization,
        category="",
        organization=task.organization,
        homepage_url="",
        base_domain="",
        trust_rating=3.0,
        source_role="",
        classification=task.classification,
        pages=[
            PageConfig(
                canonical_url=task.page_url,
                page_type=task.page_type,
                css_selectors=task.css_selectors,
                priority=task.priority,
            )
        ],
    )

    collector = get_collector(
        source_config,
        github_token=settings.github_token,
        semantic_scholar_api_key=settings.semantic_scholar_api_key,
    )
    page = collector.get_pages()[0]

    # Detect API collector
    api_types = getattr(collector, "_API_PAGE_TYPES", set())
    is_api_page = any(t in task.page_type for t in api_types)

    elapsed_ms = 0.0

    if is_api_page:
        # API path: collector.collect_page() handles its own fetch
        # snapshot_mgr is never used in the API branch, so pass None
        items, _ = await collector.collect_page(
            page,
            fetcher,
            None,  # type: ignore[arg-type]
            task.page_id or 0,
            since_date=task.since_date,
        )
        elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        return CoordFetchResult(
            task_id=task.task_id,
            organization=task.organization,
            page_url=task.page_url,
            page_type=task.page_type,
            page_id=task.page_id,
            source_id=task.source_id,
            classification=task.classification,
            items=items,
            html_content="",
            fetch_status=0,
            fetch_error=None,
            elapsed_ms=elapsed_ms,
            fetched_at=datetime.now(UTC),
            css_selectors=task.css_selectors,
            has_custom_collect=True,
            since_date=task.since_date,
            priority=task.priority,
            attempt=task.attempt,
        )

    # Standard HTML path
    fetch_result = await fetcher.fetch(task.page_url, use_browser=task.browser)
    elapsed_ms = fetch_result.elapsed_ms

    if not fetch_result.ok:
        return CoordFetchResult(
            task_id=task.task_id,
            organization=task.organization,
            page_url=task.page_url,
            page_type=task.page_type,
            page_id=task.page_id,
            source_id=task.source_id,
            classification=task.classification,
            items=[],
            html_content="",
            fetch_status=fetch_result.status_code,
            fetch_error=fetch_result.error or f"HTTP {fetch_result.status_code}",
            elapsed_ms=elapsed_ms,
            fetched_at=fetch_result.fetched_at,
            css_selectors=task.css_selectors,
            has_custom_collect=False,
            since_date=task.since_date,
            priority=task.priority,
            attempt=task.attempt,
        )

    items = collector.extract_items(fetch_result.body_text, page)
    for item in items:
        if item.page_title is None:
            item.page_title = page.page_type

    # RSS backfill: also fetch date-windowed Google News RSS
    is_google_rss = "rss" in task.page_type and "news.google.com/rss" in task.page_url
    if task.since_date and is_google_rss:
        backfill_items = await collector.collect_rss_backfill(page, fetcher, task.since_date)
        items = backfill_items + items

    return CoordFetchResult(
        task_id=task.task_id,
        organization=task.organization,
        page_url=task.page_url,
        page_type=task.page_type,
        page_id=task.page_id,
        source_id=task.source_id,
        classification=task.classification,
        items=items,
        html_content=fetch_result.body_text,
        fetch_status=fetch_result.status_code,
        fetch_error=None,
        elapsed_ms=elapsed_ms,
        fetched_at=fetch_result.fetched_at,
        css_selectors=task.css_selectors,
        has_custom_collect=False,
        since_date=task.since_date,
        priority=task.priority,
        attempt=task.attempt,
    )


async def worker_loop(
    worker_id: int,
    task_queue: asyncio.Queue[FetchTask | None],
    result_queue: asyncio.Queue[CoordFetchResult],
    fetcher: Fetcher,
    settings: PipelineSettings,
) -> None:
    """Worker loop: take tasks from queue, fetch+extract, put results. Exit on None sentinel."""
    log = logger.bind(worker_id=worker_id)
    while True:
        task = await task_queue.get()
        if task is None:
            log.debug("worker_shutdown")
            return

        try:
            result = await fetch_and_extract(task, fetcher, settings)
        except Exception as exc:
            log.warning(
                "worker_unhandled_error",
                task_id=task.task_id,
                url=task.page_url,
                error=str(exc),
            )
            result = CoordFetchResult(
                task_id=task.task_id,
                organization=task.organization,
                page_url=task.page_url,
                page_type=task.page_type,
                page_id=task.page_id,
                source_id=task.source_id,
                classification=task.classification,
                items=[],
                fetch_error=f"Worker error: {exc}",
                fetched_at=datetime.now(UTC),
                css_selectors=task.css_selectors,
                since_date=task.since_date,
                priority=task.priority,
                attempt=task.attempt,
            )

        await result_queue.put(result)
