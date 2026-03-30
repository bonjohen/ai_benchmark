"""Hugging Face leaderboard docs collector — meta-source for new community benchmarks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from ..base import RawItem, SourceCollector

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class HFLeaderboardDocsCollector(SourceCollector):
    """Collector for Hugging Face leaderboard documentation index.

    Serves as a meta-source to discover new community-driven benchmarks
    and leaderboard spaces on Hugging Face.
    """

    CONFIDENCE_TIER = "low_discovery"

    # Href patterns that indicate leaderboard/evaluation-related links
    _RELEVANT_HREF_PATTERNS = (
        "/spaces",
        "/docs/leaderboards/",
        "/docs/hub/eval",
        "leaderboard",
        "benchmark",
    )

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        # Target links in the main content area of the HF docs page
        main = soup.select_one("main, .doc-content, [role='main'], .prose")
        if main is None:
            main = soup

        seen_urls: set[str] = set()
        for link in main.select("a[href]"):
            href = str(link.get("href", ""))
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            # Filter for leaderboard/evaluation-related links
            href_lower = href.lower()
            if not any(pat in href_lower for pat in self._RELEVANT_HREF_PATTERNS):
                continue
            # Skip anchors and self-referential links
            if href.startswith("#") or href.endswith("/index"):
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)

            items.append(
                RawItem(
                    title=title,
                    url=href,
                    body=title,
                    item_type="leaderboard_space",
                    metadata={
                        "source": "hf_leaderboard_docs",
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )

        return items
