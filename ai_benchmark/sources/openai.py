"""OpenAI source collector: product newsroom, API changelog, models, pricing."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..config.settings import PageConfig
from .base import RawItem, SourceCollector


class OpenAICollector(SourceCollector):
    """Collector for OpenAI official pages."""

    def content_selectors(self, page: PageConfig) -> list[str] | None:
        if "changelog" in page.page_type:
            return ["main", ".docs-content", "[role='main']"]
        if "pricing" in page.page_type:
            return ["main", ".pricing-content", "[role='main']"]
        return None

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "changelog" in page.page_type:
            return self._extract_changelog(html)
        if "product-news" in page.page_type:
            return self._extract_newsroom(html)
        if "pricing" in page.page_type:
            return self._extract_pricing(html)
        if "system" in page.page_type:
            return self._extract_system_cards(html)
        if "model" in page.page_type:
            return self._extract_models(html)
        return []

    def _extract_changelog(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        # OpenAI changelog uses dated sections with headings or list items
        for entry in soup.select("div.entry, section, li"):
            text = entry.get_text(strip=True)
            if not text or len(text) < 10:
                continue
            items.append(
                RawItem(
                    title=text[:200],
                    body=text,
                    item_type="changelog_entry",
                    url=page_url_from_entry(entry),
                )
            )
        return items

    def _extract_newsroom(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for article in soup.select("a[href*='/news/'], article, .post-card"):
            title_el = article.select_one("h2, h3, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = article.get("href", "")
            items.append(
                RawItem(
                    title=title,
                    url=str(href),
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

    def _extract_system_cards(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for link in soup.select("a[href*='system-card'], a[href*='safety'], article"):
            title_el = link.select_one("h2, h3, .title")
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                title = link.get_text(strip=True)[:200]
            if title and len(title) > 5:
                items.append(
                    RawItem(
                        title=title,
                        url=str(link.get("href", "")),
                        body=link.get_text(strip=True),
                        item_type="system_card",
                    )
                )
        return items

    def _extract_models(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("tr, .model-card, section"):
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


def page_url_from_entry(entry) -> str:
    link = entry.select_one("a[href]")
    if link:
        return str(link.get("href", ""))
    return ""
