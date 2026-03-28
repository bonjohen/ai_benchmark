"""Cohere source collector: blog, release notes."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..config.settings import PageConfig
from .base import RawItem, SourceCollector


class CohereCollector(SourceCollector):
    """Collector for Cohere official pages."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "release" in page.page_type:
            return self._extract_release_notes(html)
        if "blog" in page.page_type:
            return self._extract_blog(html)
        return []

    def _extract_release_notes(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, h2, h3, li, .release-entry"):
            text = entry.get_text(strip=True)
            if text and len(text) > 10:
                items.append(RawItem(
                    title=text[:200],
                    body=text,
                    item_type="release_note",
                ))
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
                items.append(RawItem(
                    title=title,
                    url=str(article.get("href", "")),
                    body=article.get_text(strip=True),
                    item_type="blog_post",
                ))
        return items
