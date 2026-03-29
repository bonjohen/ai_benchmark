"""LMArena (Chatbot Arena) leaderboard collector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from . import BenchmarkCollector, LeaderboardEntry

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class LMArenaCollector(BenchmarkCollector):
    """Collector for LMArena human-preference arena leaderboard."""

    benchmark_family = "LMArena"

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        soup = BeautifulSoup(html, "lxml")
        entries: list[LeaderboardEntry] = []
        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 2:
                entries.append(
                    LeaderboardEntry(
                        model=cells[0],
                        score=cells[1],
                        rank=len(entries) + 1,
                        variant="arena_elo",
                    )
                )
        return entries
