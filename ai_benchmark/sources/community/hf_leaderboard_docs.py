"""Hugging Face leaderboard docs collector — meta-source for new community benchmarks."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


class HFLeaderboardDocsCollector(SourceCollector):
    """Collector for Hugging Face leaderboard documentation index.

    Serves as a meta-source to discover new community-driven benchmarks
    and leaderboard spaces on Hugging Face.
    """

    CONFIDENCE_TIER = "low_discovery"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []

        # Look for leaderboard space cards or links
        for card in soup.select("a[href*='/spaces/'], .space-card, article"):
            title_el = card.select_one("h3, h2, .title, p")
            if not title_el:
                # Use the link text itself
                title = card.get_text(strip=True)
            else:
                title = title_el.get_text(strip=True)

            if not title or len(title) < 5:
                continue

            href = str(card.get("href", ""))

            # Look for likes/upvotes
            likes_el = card.select_one(".likes, [data-likes]")
            likes = likes_el.get_text(strip=True) if likes_el else "0"

            items.append(RawItem(
                title=title,
                url=href,
                body=card.get_text(strip=True)[:300],
                item_type="leaderboard_space",
                metadata={
                    "source": "hf_leaderboard_docs",
                    "likes": likes,
                    "confidence_tier": self.CONFIDENCE_TIER,
                },
            ))

        return items
