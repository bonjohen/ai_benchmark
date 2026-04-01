"""OpenAI source collector: product newsroom, API changelog, models, pricing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_nextjs_rsc_payloads, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig


class OpenAICollector(SourceCollector):
    """Collector for OpenAI official pages."""

    def content_selectors(self, page: PageConfig) -> list[str] | None:
        if "changelog" in page.page_type:
            return ["main", ".docs-content", "[role='main']"]
        if "pricing" in page.page_type:
            return ["main", ".pricing-content", "[role='main']"]
        return None

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
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
                    title=extract_title(text),
                    body=text,
                    item_type="changelog_entry",
                    url=page_url_from_entry(entry),
                )
            )
        return items

    def _extract_newsroom(self, html: str) -> list[RawItem]:
        # OpenAI uses Next.js RSC streaming — article data is in script payloads
        payloads = extract_nextjs_rsc_payloads(html)
        if payloads:
            items = self._extract_newsroom_rsc(payloads)
            if items:
                return items

        # DOM fallback
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for link in soup.select("a[href*='/index/'], a[href*='/news/']"):
            title_el = link.select_one("h2, h3, span, .title")
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

    def _extract_newsroom_rsc(self, payloads: list[str]) -> list[RawItem]:
        """Extract news items from Next.js RSC payloads."""
        import re

        items: list[RawItem] = []
        for payload in payloads:
            # Look for structured post arrays (e.g. "posts":[...] or "articles":[...])
            for key in ("posts", "articles", "items", "results"):
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
                    url = slug if slug.startswith("http") else f"https://openai.com/index/{slug}"
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

        # Fallback: extract title-like strings from raw RSC text
        combined = " ".join(payloads)
        href_re = re.compile(r'/index/([a-z0-9-]+)')
        for match in href_re.finditer(combined):
            slug = match.group(1)
            # Look for nearby title text (heuristic)
            start = max(0, match.start() - 200)
            context = combined[start : match.start()]
            # Find last quoted string before the slug
            title_match = re.findall(r'"([A-Z][^"]{10,80})"', context)
            if title_match:
                items.append(
                    RawItem(
                        title=title_match[-1],
                        url=f"https://openai.com/index/{slug}",
                        item_type="news_post",
                    )
                )
        return items

    @staticmethod
    def _parse_json_array(payload: str, start: int) -> list[dict] | None:
        """Parse a JSON array starting at the given position in a payload."""
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
        import json

        try:
            return json.loads(payload[start : pos + 1])
        except (json.JSONDecodeError, ValueError):
            return None

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
            raw_text = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            title = extract_title(raw_text) if not title_el else raw_text
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
                        title=extract_title(text),
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
