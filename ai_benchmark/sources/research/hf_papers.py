"""Hugging Face Papers collector."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class HFPapersCollector(SourceCollector):
    """Collector for Hugging Face Papers and trending papers."""

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for article in soup.select("article, a[href*='/papers/'], .paper-card"):
            title_el = article.select_one("h3, h2, .title")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title:
                continue

            href = str(article.get("href", ""))
            # Try to extract arXiv ID from link
            arxiv_id = ""
            arxiv_match = re.search(r"(\d{4}\.\d{4,5})", href)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)

            # Look for upvote counts
            upvote_el = article.select_one(".upvote, .likes, [data-likes]")
            upvotes = upvote_el.get_text(strip=True) if upvote_el else "0"

            items.append(RawItem(
                title=title,
                url=href,
                body=article.get_text(strip=True),
                item_type="candidate_paper",
                metadata={
                    "arxiv_id": arxiv_id,
                    "upvotes": upvotes,
                    "source": "hf_papers",
                },
            ))

        return items
