"""Mistral AI source collector: changelog, news, pricing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class MistralCollector(SourceCollector):
    """Collector for Mistral AI official pages.

    Mistral's changelog is especially well-structured with labels like
    'MODEL RELEASED' and 'API UPDATED'.
    """

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
        if "changelog" in page.page_type:
            return self._extract_changelog(html)
        if "news" in page.page_type:
            return self._extract_news(html)
        if "pricing" in page.page_type:
            return self._extract_pricing(html)
        return []

    def _extract_changelog(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, h2, h3, li, .changelog-entry"):
            text = entry.get_text(strip=True)
            if text and len(text) > 10:
                # Mistral often uses labels like "MODEL RELEASED", "API UPDATED"
                item_type = "changelog_entry"
                text_upper = text.upper()
                if "MODEL RELEASED" in text_upper or "MODEL" in text_upper:
                    item_type = "model_release"
                elif "API UPDATED" in text_upper or "API" in text_upper:
                    item_type = "api_update"
                items.append(
                    RawItem(
                        title=extract_title(text),
                        body=text,
                        item_type=item_type,
                    )
                )
        return items

    def _extract_news(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for article in soup.select("article, a[href*='/news/'], .post-card"):
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

    def _extract_pricing(self, html: str) -> list[RawItem]:
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
