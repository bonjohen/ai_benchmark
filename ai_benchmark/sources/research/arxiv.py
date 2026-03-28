"""arXiv recent submissions collector."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class ArxivCollector(SourceCollector):
    """Collector for arXiv recent submission lists (cs.AI, cs.CL, cs.LG)."""

    # Keywords to filter for relevance to tracked models/benchmarks
    RELEVANCE_KEYWORDS = [
        "benchmark", "leaderboard", "evaluation", "language model", "llm",
        "gpt", "claude", "gemini", "llama", "mistral", "grok",
        "agent", "reasoning", "coding", "safety", "alignment",
    ]

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        for entry in soup.select("dd"):
            title_el = entry.select_one(".list-title")
            authors_el = entry.select_one(".list-authors")
            abstract_link = entry.select_one("a[href*='/abs/']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True).removeprefix("Title:").strip()
            authors = authors_el.get_text(strip=True).removeprefix("Authors:").strip() if authors_el else ""
            arxiv_url = ""
            arxiv_id = ""
            if abstract_link:
                arxiv_url = str(abstract_link.get("href", ""))
                id_match = re.search(r"(\d{4}\.\d{4,5})", arxiv_url)
                if id_match:
                    arxiv_id = id_match.group(1)

            # Basic relevance filter
            combined = f"{title} {authors}".lower()
            if not any(kw in combined for kw in self.RELEVANCE_KEYWORDS):
                continue

            items.append(RawItem(
                title=title,
                url=arxiv_url,
                body=authors,
                item_type="candidate_paper",
                metadata={"arxiv_id": arxiv_id, "authors": authors, "source": "arxiv"},
            ))

        return items
