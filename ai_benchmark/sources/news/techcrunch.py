"""TechCrunch AI category collector."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog
from bs4 import BeautifulSoup

from ..base import RawItem, SourceCollector

if TYPE_CHECKING:
    from ...config.settings import PageConfig

logger = structlog.get_logger()


class TechCrunchCollector(SourceCollector):
    """Collector for TechCrunch AI category articles.

    Medium-confidence discovery tier. Material claims from TechCrunch
    should be flagged for confirmation against primary sources.
    """

    CONFIDENCE_TIER = "medium_discovery"

    # Regex patterns for last-resort RSS item extraction from malformed XML
    _RSS_ITEM_RE = re.compile(r"<item[^>]*>(.*?)</item>", re.DOTALL)
    _RSS_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL)
    _RSS_LINK_RE = re.compile(r"<link[^>]*>(.*?)</link>", re.DOTALL)
    _RSS_PUBDATE_RE = re.compile(r"<pubDate[^>]*>(.*?)</pubDate>", re.DOTALL)

    def _regex_extract_rss(self, xml_text: str) -> list[RawItem]:
        """Last-resort regex extraction for malformed RSS XML."""
        items: list[RawItem] = []
        for block in self._RSS_ITEM_RE.findall(xml_text):
            title_m = self._RSS_TITLE_RE.search(block)
            link_m = self._RSS_LINK_RE.search(block)
            date_m = self._RSS_PUBDATE_RE.search(block)
            if not title_m:
                continue
            title = title_m.group(1).strip()
            # Strip CDATA wrappers
            title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title).strip()
            if not title:
                continue
            link = link_m.group(1).strip() if link_m else ""
            date_text = date_m.group(1).strip() if date_m else None
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    date_text=date_text,
                    body="",
                    item_type="news_article",
                    metadata={
                        "source": "techcrunch",
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )
        return items

    def _extract_rss(self, xml_text: str) -> list[RawItem]:
        """Parse TechCrunch WordPress RSS feed."""
        # Strip BOM if present
        clean = xml_text.lstrip("\ufeff").strip()
        soup = BeautifulSoup(clean, "lxml-xml")
        items: list[RawItem] = []
        rss_items = soup.find_all("item")
        if not rss_items:
            # Fallback: lxml-xml may fail if content is not well-formed XML.
            # Retry with the lxml HTML parser which is more lenient.
            logger.warning("rss_xml_parse_empty", parser="lxml-xml", source="techcrunch")
            soup = BeautifulSoup(clean, "lxml")
            rss_items = soup.find_all("item")
        if not rss_items:
            # Last resort: regex-based extraction for severely malformed XML
            logger.warning("rss_html_parse_empty", parser="lxml", source="techcrunch")
            return self._regex_extract_rss(clean)
        for item in rss_items:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            creator_el = item.find("dc:creator")
            desc_el = item.find("description")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue
            link = link_el.get_text(strip=True) if link_el else ""
            date_text = pub_date_el.get_text(strip=True) if pub_date_el else None
            author = creator_el.get_text(strip=True) if creator_el else None
            body = ""
            if desc_el:
                desc_soup = BeautifulSoup(desc_el.get_text(), "lxml")
                body = desc_soup.get_text(strip=True)[:500]
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    date_text=date_text,
                    body=body,
                    item_type="news_article",
                    metadata={
                        "source": "techcrunch",
                        "author": author,
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )
        return items

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_rss(html)
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for article in soup.select("article, .post-block, [class*='post-card']"):
            title_el = article.select_one("h2, h3, .post-block__title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = ""
            link = title_el if title_el.name == "a" else title_el.find("a")
            if link:
                href = str(link.get("href", ""))

            date_el = article.select_one("time, .river-byline__time")
            date_text = date_el.get_text(strip=True) if date_el else None

            author_el = article.select_one(".river-byline__authors a, [rel='author']")
            author = author_el.get_text(strip=True) if author_el else None

            items.append(
                RawItem(
                    title=title,
                    url=href,
                    date_text=date_text,
                    body=article.get_text(strip=True)[:500],
                    item_type="news_article",
                    metadata={
                        "source": "techcrunch",
                        "author": author,
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items
