"""xAI source collector: release notes, models/pricing, news."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class XAICollector(SourceCollector):
    """Collector for xAI official pages."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "release" in page.page_type:
            return self._extract_release_notes(html)
        if "model" in page.page_type or "pricing" in page.page_type:
            return self._extract_models_pricing(html)
        if "news" in page.page_type:
            return self._extract_news(html)
        return []

    def _extract_release_notes(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("section, h2, h3, .release-entry"):
            text = section.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="release_note",
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
        for article in soup.select("article, a[href*='/news'], .post-card"):
            title_el = article.select_one("h2, h3, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if title:
                items.append(
                    RawItem(
                        title=title,
                        url=str(article.get("href", "")),
                        body=article.get_text(strip=True),
                        item_type="news_post",
                    )
                )
        return items
