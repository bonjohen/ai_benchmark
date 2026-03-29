"""Reuters AI news collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class ReutersCollector(SourceCollector):
    """Collector for Reuters technology/AI news.

    High-confidence secondary tier source. Articles here carry weight
    for confirming company announcements but are not primary sources.
    """

    CONFIDENCE_TIER = "high_secondary"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        # Reuters uses article elements and heading links
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
