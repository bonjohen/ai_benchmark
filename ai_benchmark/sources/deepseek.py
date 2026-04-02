"""DeepSeek source collector: API docs, models/pricing, changelog, news."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class DeepSeekCollector(SourceCollector):
    """Collector for DeepSeek official pages."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
        if "changelog" in page.page_type or "release" in page.page_type:
            return self._extract_changelog(html)
        if "pricing" in page.page_type or "model" in page.page_type:
            return self._extract_models_pricing(html)
        if "news" in page.page_type or "blog" in page.page_type:
            return self._extract_news(html)
        # Generic fallback: extract table rows
        return self._extract_models_pricing(html)

    def _extract_changelog(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, h2, h3, article, .changelog-entry, div.entry"):
            text = entry.get_text(strip=True)
            if not text or len(text) < 15:
                continue
            # Look for date patterns in the text
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
            items.append(
                RawItem(
                    title=extract_title(text),
                    body=text[:500],
                    date_text=date_match.group(0) if date_match else None,
                    item_type="changelog_entry",
                )
            )
        return items

    def _extract_models_pricing(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td, th")]
            if len(cells) >= 2:
                items.append(
                    RawItem(
                        title=cells[0],
                        body=" | ".join(cells),
                        item_type="pricing_row",
                        model_hint=cells[0] if cells[0] else None,
                    )
                )
        return items

    def _extract_news(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for link in soup.select("a[href*='/news/'], a[href*='/blog/'], article, .post-card"):
            title_el = link.select_one("h2, h3, h4, span, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = link.get("href", "")
            items.append(
                RawItem(
                    title=title,
                    url=str(href),
                    body=link.get_text(strip=True),
                    item_type="news_post",
                )
            )
        return items
