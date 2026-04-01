"""xAI source collector: release notes, models/pricing, news."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_nextjs_rsc_payloads, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class XAICollector(SourceCollector):
    """Collector for xAI official pages."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
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
                        title=extract_title(text),
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
        # Try RSC payload extraction first (x.ai may use Next.js)
        payloads = extract_nextjs_rsc_payloads(html)
        if payloads:
            items = self._extract_news_rsc(payloads)
            if items:
                return items

        # DOM fallback with broader selectors
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        # Try structured link elements first
        for link in soup.select("a[href*='/news/']"):
            title_el = link.select_one("h2, h3, h4, span, p, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = link.get("href", "")
            url = href if str(href).startswith("http") else f"https://x.ai{href}"
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    body=link.get_text(strip=True),
                    item_type="news_post",
                )
            )

        if not items:
            # Broader fallback: article containers
            for article in soup.select("article, .post-card, [class*='card'], [class*='post']"):
                title_el = article.select_one("h2, h3, h4, span, .title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                link_el = article.select_one("a[href]")
                href = str(link_el.get("href", "")) if link_el else ""
                items.append(
                    RawItem(
                        title=title,
                        url=href,
                        body=article.get_text(strip=True),
                        item_type="news_post",
                    )
                )

        return items

    def _extract_news_rsc(self, payloads: list[str]) -> list[RawItem]:
        """Extract news items from Next.js RSC payloads."""
        items: list[RawItem] = []
        for payload in payloads:
            for key in ("posts", "articles", "items", "news"):
                pattern = re.search(rf'"{key}":\[', payload)
                if not pattern:
                    continue
                arr = self._parse_json_array(payload, pattern.start() + len(key) + 3)
                if not arr:
                    continue
                for post in arr:
                    if not isinstance(post, dict):
                        continue
                    title = (post.get("title") or post.get("name") or "").strip()
                    slug = post.get("slug") or post.get("href") or ""
                    if not title:
                        continue
                    date_raw = post.get("date") or post.get("publishedAt") or ""
                    date_text = date_raw[:10] if date_raw else None
                    description = post.get("description") or post.get("excerpt") or ""
                    url = slug if slug.startswith("http") else f"https://x.ai/news/{slug}"
                    items.append(
                        RawItem(
                            title=title,
                            url=url,
                            date_text=date_text,
                            body=f"{title} — {description}" if description else title,
                            item_type="news_post",
                        )
                    )
                if items:
                    return items
        return items

    @staticmethod
    def _parse_json_array(payload: str, start: int) -> list[dict] | None:
        """Parse a JSON array starting at the given position."""
        depth = 0
        for pos in range(start, len(payload)):
            if payload[pos] == "[":
                depth += 1
            elif payload[pos] == "]":
                depth -= 1
                if depth == 0:
                    break
        else:
            return None
        try:
            return json.loads(payload[start : pos + 1])
        except (json.JSONDecodeError, ValueError):
            return None
