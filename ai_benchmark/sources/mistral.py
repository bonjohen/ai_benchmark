"""Mistral AI source collector: changelog, news, pricing, model catalog."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .base import RawItem, SourceCollector, extract_nextjs_rsc_payloads, extract_title

if TYPE_CHECKING:
    from ..config.settings import PageConfig

# Badge type to item_type mapping for changelog entries
_BADGE_TYPE_MAP = {
    "model": "model_release",
    "api": "api_update",
    "security": "api_update",
    "other": "changelog_entry",
}

# Regex to extract changelog entry dates from RSC payloads
_RSC_DATE_RE = re.compile(r'"date":"(\d{4}-\d{2}-\d{2})"')

# Regex to extract badge types from RSC payloads
_RSC_BADGE_TYPE_RE = re.compile(r'"data-badge-type":"([^"]*)"')

# Regex to extract plain text content from RSC payloads.
# Matches quoted strings that are NOT JSON keys (no colon after) and NOT
# CSS class names or React internals. Filters in _is_content_text().
_RSC_TEXT_RE = re.compile(r'(?<!\w)"([^"]{10,})"(?!\s*:)')

# Regex to extract model code slugs from RSC payloads (inside <code> elements)
_RSC_CODE_RE = re.compile(r'"children":"([\w-]+-\d{4}[a-z]?)"')

# CSS-like tokens that indicate a string is a class name, not content
_CSS_TOKENS = re.compile(
    r"(?:inline-(?:flex|block)|flex-(?:col|row|1)|"
    r"shrink-\d|hidden\s+\w{2}:|"
    r"(?:bg|text|border|ring|gap|size|font|rounded|px|py|mb|mt|mr|ml|"
    r"lg|xl|sm|md|min|max|top|left|right|bottom|w|h|p)-)"
)

# Badge label strings that should be stripped from content text
_BADGE_LABELS = {"MODEL RELEASED", "API UPDATED", "SECURITY UPDATE", "OTHER"}

# Month labels used in changelog navigation — not content
_MONTH_LABEL_RE = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{2,4}$"
)


def _is_content_text(text: str) -> bool:
    """Return True if text is human-readable content, not CSS/React internals."""
    if not text or len(text) < 10:
        return False
    # Skip React component references, JS chunks, hash-like strings
    if text.startswith(("$", "I[", "static/", "/_next/", "[&")):
        return False
    # Skip page header/description boilerplate
    if "filter by date and type" in text.lower():
        return False
    # Skip month labels used in changelog navigation
    if _MONTH_LABEL_RE.match(text):
        return False
    # Skip strings dominated by CSS tokens
    css_hits = len(_CSS_TOKENS.findall(text))
    words = text.split()
    if css_hits >= 2 or (css_hits >= 1 and len(words) < 5):
        return False
    # Must contain at least one space (real sentences do)
    return " " in text


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
        if "model" in page.page_type:
            return self._extract_model_docs(html)
        return []

    def _extract_changelog(self, html: str) -> list[RawItem]:
        payloads = extract_nextjs_rsc_payloads(html)
        if not payloads:
            return self._extract_changelog_fallback(html)

        items: list[RawItem] = []
        # Each changelog entry payload contains a date, text content,
        # and badge types in serialized React virtual DOM format.
        for payload in payloads:
            if "changelog-content" not in payload:
                continue

            # Extract the entry date
            date_match = _RSC_DATE_RE.search(payload)
            date_text = date_match.group(1) if date_match else None

            # Extract all badge types in this entry
            badge_types = _RSC_BADGE_TYPE_RE.findall(payload)

            # Extract text content — collect readable strings from the payload
            texts = self._extract_rsc_text_content(payload)
            if not texts:
                continue

            # Each badge corresponds to a separate changelog item within the entry
            if badge_types:
                # Split items by badge: each badge gets the text preceding it
                segments = self._split_changelog_by_badges(payload, badge_types)
                for text, badge in segments:
                    item_type = _BADGE_TYPE_MAP.get(badge, "changelog_entry")
                    # Extract model code if present
                    code_match = _RSC_CODE_RE.search(text) if text else None
                    model_hint = code_match.group(1) if code_match else None
                    clean_text = self._clean_rsc_text(text)
                    if clean_text and len(clean_text) > 10:
                        items.append(
                            RawItem(
                                title=extract_title(clean_text),
                                body=clean_text,
                                date_text=date_text,
                                item_type=item_type,
                                model_hint=model_hint,
                            )
                        )
            else:
                # No badges — treat the entire entry as a single changelog item
                full_text = " ".join(texts)
                if len(full_text) > 10:
                    items.append(
                        RawItem(
                            title=extract_title(full_text),
                            body=full_text,
                            date_text=date_text,
                            item_type="changelog_entry",
                        )
                    )

        return items

    @staticmethod
    def _extract_rsc_text_content(payload: str) -> list[str]:
        """Extract readable text strings from an RSC payload."""
        texts = []
        for m in _RSC_TEXT_RE.finditer(payload):
            text = m.group(1).strip()
            if _is_content_text(text):
                texts.append(text)
        return texts

    @staticmethod
    def _split_changelog_by_badges(payload: str, badge_types: list[str]) -> list[tuple[str, str]]:
        """Split a changelog payload into (text_segment, badge_type) pairs."""
        segments: list[tuple[str, str]] = []
        # Find positions of each badge-type declaration
        badge_positions = [(m.start(), m.group(1)) for m in _RSC_BADGE_TYPE_RE.finditer(payload)]
        for idx, (pos, badge) in enumerate(badge_positions):
            # Text for this item is between previous badge (or start) and this badge
            start = badge_positions[idx - 1][0] if idx > 0 else 0
            segment = payload[start:pos]
            segments.append((segment, badge))
        return segments

    @staticmethod
    def _clean_rsc_text(segment: str) -> str:
        """Extract readable text from an RSC payload segment."""
        texts = []
        for m in _RSC_TEXT_RE.finditer(segment):
            text = m.group(1).strip()
            if _is_content_text(text) and text not in _BADGE_LABELS:
                texts.append(text)
        return " ".join(texts)

    @staticmethod
    def _extract_changelog_fallback(html: str) -> list[RawItem]:
        """DOM-based fallback for when RSC payloads are absent."""
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for entry in soup.select("section, h2, h3, li, .changelog-entry"):
            text = entry.get_text(strip=True)
            if text and len(text) > 10:
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
        payloads = extract_nextjs_rsc_payloads(html)
        if not payloads:
            return self._extract_news_fallback(html)

        # RSC payloads contain a "posts":[...] JSON array with structured data
        items: list[RawItem] = []
        for payload in payloads:
            posts_match = re.search(r'"posts":\[', payload)
            if not posts_match:
                continue
            posts = self._parse_json_array(payload, posts_match.start() + 8)
            if not posts:
                continue
            for post in posts:
                if not isinstance(post, dict):
                    continue
                slug = post.get("slug", "")
                title = post.get("title", "").strip()
                if not title or not slug:
                    continue
                date_raw = post.get("date", "")
                date_text = date_raw[:10] if date_raw else None
                description = post.get("description") or ""
                category = ""
                cat = post.get("category")
                if isinstance(cat, dict):
                    category = cat.get("name", "")
                body_parts = [title]
                if description:
                    body_parts.append(description)
                if category:
                    body_parts.append(f"[{category}]")
                items.append(
                    RawItem(
                        title=title,
                        url=f"https://mistral.ai/news/{slug}",
                        date_text=date_text,
                        body=" — ".join(body_parts),
                        item_type="news_post",
                    )
                )
            break  # Only need the first posts array
        return items or self._extract_news_fallback(html)

    @staticmethod
    def _parse_json_array(payload: str, start: int) -> list[dict] | None:
        """Parse a JSON array starting at the given position in a payload."""
        depth = 0
        pos = start
        for pos in range(start, len(payload)):
            if payload[pos] == "[":
                depth += 1
            elif payload[pos] == "]":
                depth -= 1
                if depth == 0:
                    break
        array_str = payload[start : pos + 1]
        try:
            return json.loads(array_str)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _extract_news_fallback(html: str) -> list[RawItem]:
        """DOM-based fallback for when RSC payloads are absent."""
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

    def _extract_model_docs(self, html: str) -> list[RawItem]:
        payloads = extract_nextjs_rsc_payloads(html)
        if not payloads:
            return self._extract_model_docs_fallback(html)

        items: list[RawItem] = []
        # Each model has its own payload with an h3 heading and description text.
        # Pattern: ["$","h3",null,{..."children":"Model Name"}]
        h3_re = re.compile(r'\["\$","h3",null,\{[^}]*"children":"([^"]{3,100})"')
        seen_names: set[str] = set()

        for payload in payloads:
            h3_match = h3_re.search(payload)
            if not h3_match:
                continue
            model_name = h3_match.group(1).strip()
            if not model_name or model_name in seen_names:
                continue
            # Skip navigation/footer headings
            if model_name.isupper() or model_name in (
                "Help Center",
                "Cookbooks",
                "AI Studio",
                "Discord",
            ):
                continue
            seen_names.add(model_name)

            # Extract description text from the same payload
            descriptions = []
            for m in _RSC_TEXT_RE.finditer(payload):
                text = m.group(1).strip()
                if _is_content_text(text) and text != model_name:
                    descriptions.append(text)

            body = " ".join(descriptions) if descriptions else model_name
            items.append(
                RawItem(
                    title=model_name,
                    body=body,
                    item_type="model_entry",
                    model_hint=model_name,
                )
            )

        return items or self._extract_model_docs_fallback(html)

    @staticmethod
    def _extract_model_docs_fallback(html: str) -> list[RawItem]:
        """DOM-based fallback for when RSC payloads are absent."""
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

    def _extract_pricing(self, html: str) -> list[RawItem]:
        # Try DOM-based table extraction first (works if page has <table> elements)
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
        # Pricing is also captured via RSS — return whatever we found
        return items
