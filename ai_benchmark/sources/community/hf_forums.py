"""Hugging Face Forums minimal metadata collector."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class HFForumsCollector(SourceCollector):
    """Collector for Hugging Face community forums.

    Discovery-only source: ingests only minimal metadata (title, author,
    timestamp, tags, outbound links). Full content is not stored.
    """

    CONFIDENCE_TIER = "low_discovery"

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

            items.append(RawItem(
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
            ))

        return items
