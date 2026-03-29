"""Google/Gemini source collector: release notes, pricing, models, DeepMind blog."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..config.settings import PageConfig
from .base import RawItem, SourceCollector


class GoogleCollector(SourceCollector):
    """Collector for Google Gemini API and DeepMind pages."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "changelog" in page.page_type:
            return self._extract_changelog(html)
        if "pricing" in page.page_type:
            return self._extract_pricing(html)
        if "rate limit" in page.page_type:
            return self._extract_rate_limits(html)
        if "model" in page.page_type:
            return self._extract_models(html)
        if "blog" in page.page_type:
            return self._extract_blog(html)
        return []

    def _extract_changelog(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("section, h2, h3"):
            text = section.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="changelog_entry",
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

    def _extract_rate_limits(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td, th")]
            if len(cells) >= 2:
                items.append(
                    RawItem(
                        title=cells[0],
                        body=" | ".join(cells),
                        item_type="rate_limit_entry",
                        model_hint=cells[0] if cells[0] else None,
                    )
                )
        return items

    def _extract_models(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for el in soup.select("tr, .model-card, section, h3"):
            text = el.get_text(strip=True)
            if text and len(text) > 5:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="model_entry",
                    )
                )
        return items

    def _extract_blog(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for article in soup.select("article, a[href*='/blog/'], .post-card"):
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
                        item_type="blog_post",
                    )
                )
        return items
