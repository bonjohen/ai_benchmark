"""Anthropic source collector: newsroom, system cards, models, pricing, release notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class AnthropicCollector(SourceCollector):
    """Collector for Anthropic official pages."""

    def content_selectors(self, page: PageConfig) -> list[str] | None:
        if "system-card" in page.page_type:
            return ["main", ".content", "[role='main']"]
        return None

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "newsroom" in page.page_type:
            return self._extract_newsroom(html)
        if "system-card" in page.page_type:
            return self._extract_system_cards(html)
        if "release" in page.page_type:
            return self._extract_release_notes(html)
        if "pricing" in page.page_type:
            return self._extract_pricing(html)
        if "model" in page.page_type:
            return self._extract_models(html)
        return []

    def _extract_newsroom(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for article in soup.select("a[href*='/news/'], article, .post-card, .card"):
            title_el = article.select_one("h2, h3, .title, span")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue
            items.append(
                RawItem(
                    title=title,
                    url=str(article.get("href", "")),
                    body=article.get_text(strip=True),
                    item_type="news_post",
                )
            )
        return items

    def _extract_system_cards(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for card in soup.select("a[href*='system-card'], .card, li"):
            text = card.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=text[:200],
                        url=str(card.get("href", "")),
                        body=text,
                        item_type="system_card",
                    )
                )
        return items

    def _extract_release_notes(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, .changelog-entry, div.entry, li"):
            text = entry.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="release_note",
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

    def _extract_models(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("tr, .model-card, section, h3"):
            text = section.get_text(strip=True)
            if text and len(text) > 5:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="model_entry",
                    )
                )
        return items
