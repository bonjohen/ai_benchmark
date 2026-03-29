"""Reuters AI news collector via Google News RSS proxy."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from ..base import RawItem, SourceCollector

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class ReutersCollector(SourceCollector):
    """Collector for Reuters technology/AI news.

    Reuters direct pages require authentication, so we collect via
    Google News RSS filtered to site:reuters.com. Articles here carry
    weight for confirming company announcements (high_secondary tier).
    """

    CONFIDENCE_TIER = "high_secondary"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_rss(html)
        return self._extract_html(html)

    def _extract_rss(self, xml_text: str) -> list[RawItem]:
        """Parse Google News RSS feed for Reuters articles."""
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
            # Strip " - Reuters" suffix added by Google News
            title = re.sub(r"\s*-\s*Reuters\s*$", "", title)
            if not title:
                continue

            link = link_el.get_text(strip=True) if link_el else ""
            date_text = pub_date_el.get_text(strip=True) if pub_date_el else None

            # Extract plain text from HTML description
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
                    metadata={
                        "source": "reuters",
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items

    def _extract_html(self, html: str) -> list[RawItem]:
        """Fallback HTML parser for direct Reuters pages."""
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for article in soup.select("article, [data-testid='MediaStoryCard'], .story-card"):
            title_el = article.select_one("h3, h2, a[data-testid='Heading']")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = ""
            link = title_el if title_el.name == "a" else title_el.find_parent("a")
            if link:
                href = str(link.get("href", ""))

            date_el = article.select_one("time, [data-testid='Label'], .date")
            date_text = date_el.get_text(strip=True) if date_el else None

            items.append(
                RawItem(
                    title=title,
                    url=href,
                    date_text=date_text,
                    body=article.get_text(strip=True)[:500],
                    item_type="news_article",
                    metadata={
                        "source": "reuters",
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items
