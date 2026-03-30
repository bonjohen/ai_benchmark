"""Hugging Face Forums minimal metadata collector."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog
from bs4 import BeautifulSoup

from ..base import RawItem, SourceCollector

logger = structlog.get_logger()

if TYPE_CHECKING:
    from datetime import date

    from ...collection.differ import DiffResult
    from ...collection.fetcher import Fetcher
    from ...collection.snapshot import SnapshotManager
    from ...config.settings import PageConfig

# Support/help thread patterns to filter out.
# Only match clearly support-oriented threads; avoid broad patterns like
# "error" or "how do" that also match legitimate technical discussion.
SUPPORT_THREAD_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bhelp\b.*\b(run|install|setup|configure)\b", re.IGNORECASE),
    re.compile(r"\bnot working\b", re.IGNORECASE),
    re.compile(r"\bcan'?t\b.*\b(run|install|load)\b", re.IGNORECASE),
]


def _is_support_thread(title: str) -> bool:
    """Check if a topic title matches support/help thread patterns."""
    return any(p.search(title) for p in SUPPORT_THREAD_PATTERNS)


class HFForumsCollector(SourceCollector):
    """Collector for Hugging Face community forums.

    Discovery-only source: ingests only minimal metadata (title, author,
    timestamp, tags, outbound links). Full content is not stored.
    Filters out support/help threads.
    """

    CONFIDENCE_TIER = "low_discovery"

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Override to use Discourse JSON API for json pages."""
        if "discourse json" in page.page_type:
            result = await fetcher.fetch(page.canonical_url)
            if not result.ok:
                logger.warning(
                    "discourse_fetch_failed",
                    url=page.canonical_url,
                    status=result.status_code,
                    error=result.error,
                )
                return [], None
            return self._extract_discourse_json(result.body_text), None
        return await super().collect_page(
            page,
            fetcher,
            snapshot_mgr,
            page_id,
            since_date=since_date,
        )

    def _extract_discourse_json(self, body: str) -> list[RawItem]:
        """Parse Discourse /latest.json API response."""
        items: list[RawItem] = []
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return items
        topics = data.get("topic_list", {}).get("topics", [])
        for topic in topics:
            title = topic.get("title", "")
            if not title or _is_support_thread(title):
                continue
            slug = topic.get("slug", "")
            topic_id = topic.get("id", "")
            url = f"https://discuss.huggingface.co/t/{slug}/{topic_id}" if slug else ""
            tags = topic.get("tags", [])
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    date_text=topic.get("created_at", ""),
                    body="",
                    item_type="forum_topic",
                    metadata={
                        "source": "hf_forums",
                        "tags": tags,
                        "reply_count": topic.get("reply_count", 0),
                        "views": topic.get("views", 0),
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )
        return items

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for topic in soup.select("tr.topic-list-item, .topic-list-item, [data-topic-id]"):
            title_el = topic.select_one("a.title, .link-top-line a, a.raw-topic-link")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            if _is_support_thread(title):
                continue

            href = str(title_el.get("href", ""))

            # Extract tags
            tag_els = topic.select(".discourse-tag, .badge-category__name")
            tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

            # Extract author
            author_el = topic.select_one("a[data-user-card], .creator a")
            author = author_el.get_text(strip=True) if author_el else None

            # Extract reply count / activity
            activity_el = topic.select_one(".num.activity a, .posts")
            activity = activity_el.get_text(strip=True) if activity_el else None

            # Extract outbound links from snippet
            outbound_links = []
            for link in topic.select("a[href]"):
                link_href = str(link.get("href", ""))
                if link_href.startswith("http") and "huggingface.co/discuss" not in link_href:
                    outbound_links.append(link_href)

            items.append(
                RawItem(
                    title=title,
                    url=href,
                    body="",  # minimal metadata only
                    item_type="forum_topic",
                    metadata={
                        "source": "hf_forums",
                        "author": author,
                        "tags": tags,
                        "outbound_links": outbound_links[:5],
                        "activity": activity,
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items
