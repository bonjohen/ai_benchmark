"""Abstract base class for source collectors."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from ..collection.differ import DiffResult
from ..collection.fetcher import FetchResult, Fetcher
from ..collection.snapshot import SnapshotManager
from ..config.settings import PageConfig, SourceConfig

logger = structlog.get_logger()


@dataclass
class RawItem:
    """A raw extracted item from a source page before normalization."""

    title: str
    url: str = ""
    date_text: str | None = None
    body: str = ""
    model_hint: str | None = None
    item_type: str = "unknown"
    page_title: str | None = None
    metadata: dict = field(default_factory=dict)


class SourceCollector(abc.ABC):
    """Abstract base for all source collectors.

    Subclasses implement `extract_items()` to parse page-specific HTML
    into RawItem objects. The base class handles fetching, diffing, and
    snapshot management.
    """

    source_config: SourceConfig

    def __init__(self, source_config: SourceConfig):
        self.source_config = source_config

    def get_pages(self) -> list[PageConfig]:
        """Return the pages this collector is responsible for."""
        return self.source_config.pages

    @abc.abstractmethod
    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        """Extract raw items from page HTML. Implement per source."""
        ...

    def content_selectors(self, page: PageConfig) -> list[str] | None:
        """Return CSS selectors for main content extraction. Override per source."""
        return None

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Fetch a page, compare with previous snapshot, extract items if changed."""
        log = logger.bind(source=self.source_config.source_name, url=page.canonical_url)

        result: FetchResult = await fetcher.fetch(page.canonical_url)
        if not result.ok:
            log.warning("fetch_failed", status=result.status_code, error=result.error)
            return [], None

        diff, _snapshot = await snapshot_mgr.compare_with_latest(
            page_id, result.body_text, self.content_selectors(page)
        )

        if not diff.changed:
            log.debug("no_change")
            return [], diff

        items = self.extract_items(result.body_text, page)
        for item in items:
            if item.page_title is None:
                item.page_title = page.page_type
        log.info("items_extracted", count=len(items), change_ratio=diff.change_ratio)
        return items, diff
