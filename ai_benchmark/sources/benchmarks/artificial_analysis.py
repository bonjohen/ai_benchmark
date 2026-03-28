"""Artificial Analysis leaderboard collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from . import BenchmarkCollector, LeaderboardEntry


class ArtificialAnalysisCollector(BenchmarkCollector):
    """Collector for Artificial Analysis performance leaderboard."""

    benchmark_family = "Artificial Analysis"

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        if "methodology" in page.page_type:
            return []
        soup = BeautifulSoup(html, "lxml")
        entries: list[LeaderboardEntry] = []
        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 2:
                entries.append(LeaderboardEntry(
                    model=cells[0],
                    score=cells[1],
                    rank=len(entries) + 1,
                    variant="performance",
                ))
        return entries
