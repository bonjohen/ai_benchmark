"""Cohere source collector: blog, release notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig

logger = structlog.get_logger()


class CohereCollector(SourceCollector):
    """Collector for Cohere official pages.

    Cohere's HTML pages are JS-rendered shells (Mintlify docs, Next.js + Sanity
    CMS blog) that return no extractable content. The Google News RSS feed is
    the primary collection path. HTML extraction methods are retained as
    fallbacks in case Cohere adds server-side rendering.
    """

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
        if "release" in page.page_type:
            items = self._extract_release_notes(html)
        elif "blog" in page.page_type:
            items = self._extract_blog(html)
        elif "pricing" in page.page_type:
            items = self._extract_pricing(html)
        elif "model" in page.page_type:
            items = self._extract_model_docs(html)
        else:
            return []
        if not items:
            logger.debug(
                "cohere_html_extraction_empty",
                page_type=page.page_type,
                note="Expected: Cohere pages are JS-rendered shells. RSS is primary.",
            )
        return items

    def _extract_release_notes(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, h2, h3, li, .release-entry"):
            text = entry.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=extract_title(text),
                        body=text,
                        item_type="release_note",
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

    def _extract_model_docs(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("tr, .model-card, section, h3"):
            text = section.get_text(strip=True)
            if text and len(text) > 5:
                items.append(
                    RawItem(
                        title=extract_title(text),
                        body=text,
                        item_type="model_entry",
                    )
                )
        return items
