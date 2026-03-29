"""TechCrunch AI category collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class TechCrunchCollector(SourceCollector):
    """Collector for TechCrunch AI category articles.

    Medium-confidence discovery tier. Material claims from TechCrunch
    should be flagged for confirmation against primary sources.
    """

    CONFIDENCE_TIER = "medium_discovery"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for article in soup.select("article, .post-block, [class*='post-card']"):
            title_el = article.select_one("h2, h3, .post-block__title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = ""
            link = title_el if title_el.name == "a" else title_el.find("a")
            if link:
                href = str(link.get("href", ""))

            date_el = article.select_one("time, .river-byline__time")
            date_text = date_el.get_text(strip=True) if date_el else None

            author_el = article.select_one(".river-byline__authors a, [rel='author']")
            author = author_el.get_text(strip=True) if author_el else None

            items.append(
                RawItem(
                    title=title,
                    url=href,
                    date_text=date_text,
                    body=article.get_text(strip=True)[:500],
                    item_type="news_article",
                    metadata={
                        "source": "techcrunch",
                        "author": author,
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items
