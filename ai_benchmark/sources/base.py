"""Abstract base class for source collectors."""

from __future__ import annotations

import abc
import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import structlog
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from ..collection.differ import DiffResult
    from ..collection.fetcher import Fetcher, FetchResult
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

    def _extract_google_news_rss(self, xml_text: str) -> list[RawItem]:
        """Parse a Google News RSS feed. Reusable by any collector with RSS pages."""
        soup = BeautifulSoup(xml_text, "lxml-xml")
        items: list[RawItem] = []
        for item in soup.find_all("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            description_el = item.find("description")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            # Strip common suffixes added by Google News
            title = re.sub(r"\s*-\s*[\w\s]+$", "", title)
            if not title:
                continue
            link = link_el.get_text(strip=True) if link_el else ""
            date_text = pub_date_el.get_text(strip=True) if pub_date_el else None
            body = ""
            if description_el:
                desc_soup = BeautifulSoup(description_el.get_text(), "lxml")
                body = desc_soup.get_text(strip=True)[:500]
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    date_text=date_text,
                    body=body,
                    item_type="news_article",
                )
            )
        return items

    def content_selectors(self, page: PageConfig) -> list[str] | None:
        """Return CSS selectors for main content extraction. Override per source."""
        return None

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Fetch a page, compare with previous snapshot, extract items if changed."""
        log = logger.bind(source=self.source_config.source_name, url=page.canonical_url)

        # For Google News RSS backfill, fetch date-windowed queries
        is_google_rss = "rss" in page.page_type and "news.google.com/rss" in page.canonical_url
        if since_date and is_google_rss:
            backfill_items = await self.collect_rss_backfill(page, fetcher, since_date)
            # Also run the normal fetch to get latest results and maintain snapshots
            normal_items, diff = await self._collect_page_inner(
                page,
                fetcher,
                snapshot_mgr,
                page_id,
                since_date,
            )
            combined = backfill_items + normal_items
            if combined:
                log.info(
                    "items_extracted",
                    count=len(combined),
                    backfill_items=len(backfill_items),
                )
            return combined, diff

        return await self._collect_page_inner(
            page,
            fetcher,
            snapshot_mgr,
            page_id,
            since_date,
        )

    async def _collect_page_inner(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Core page collection: fetch, diff, extract, filter."""
        log = logger.bind(source=self.source_config.source_name, url=page.canonical_url)

        result: FetchResult = await fetcher.fetch(page.canonical_url)
        if not result.ok:
            log.warning("fetch_failed", status=result.status_code, error=result.error)
            return [], None

        diff, _snapshot = await snapshot_mgr.compare_with_latest(
            page_id, result.body_text, self.content_selectors(page)
        )

        if not diff.changed:
            if since_date:
                # Backfill mode: force re-extraction even if content unchanged
                log.debug("backfill_reextract")
            else:
                log.debug("no_change")
                return [], diff

        items = self.extract_items(result.body_text, page)
        for item in items:
            if item.page_title is None:
                item.page_title = page.page_type

        # In backfill mode, skip quality filtering — the user explicitly
        # requested historical data, so stale-date checks are counterproductive.
        if not since_date:
            from ..processing.quality_filter import is_low_value_page

            if is_low_value_page(diff, items, page):
                log.warning("low_value_page_filtered", count=len(items))
                return [], diff

        log.info("items_extracted", count=len(items), change_ratio=diff.change_ratio)
        return items, diff

    async def collect_rss_backfill(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        since_date: date,
    ) -> list[RawItem]:
        """Fetch date-windowed Google News RSS feeds for historical backfill."""
        log = logger.bind(source=self.source_config.source_name)
        windowed_urls = self._make_rss_date_windows(page.canonical_url, since_date)
        all_items: list[RawItem] = []

        for url in windowed_urls:
            result: FetchResult = await fetcher.fetch(url)
            if result.ok:
                items = self._extract_google_news_rss(result.body_text)
                for item in items:
                    if item.page_title is None:
                        item.page_title = page.page_type
                log.info("backfill_window_fetched", url=url, count=len(items))
                all_items.extend(items)
            else:
                log.warning("backfill_window_failed", url=url, status=result.status_code)
            # Rate-limit delay between Google News requests
            await asyncio.sleep(1.0)

        return all_items

    @staticmethod
    def _make_rss_date_windows(url: str, since_date: date) -> list[str]:
        """Generate monthly Google News RSS URLs with after:/before: date filters."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        base_q = params.get("q", [""])[0]
        tomorrow = date.today() + timedelta(days=1)

        windows: list[str] = []
        start = since_date
        while start < tomorrow:
            # First day of next month
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1)
            else:
                end = start.replace(month=start.month + 1, day=1)
            end = min(end, tomorrow)

            windowed_q = f"{base_q} after:{start.isoformat()} before:{end.isoformat()}"
            new_params = {**params, "q": [windowed_q]}
            new_query = urlencode(new_params, doseq=True)
            windows.append(urlunparse(parsed._replace(query=new_query)))
            start = end

        return windows
