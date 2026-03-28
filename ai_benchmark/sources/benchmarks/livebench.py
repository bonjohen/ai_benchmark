"""LiveBench leaderboard and methodology collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem
from . import BenchmarkCollector, LeaderboardEntry


class LiveBenchCollector(BenchmarkCollector):
    """Collector for LiveBench contamination-resistant benchmark."""

    benchmark_family = "LiveBench"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "methodology" in page.page_type or "pdf" in page.page_type:
            return [RawItem(
                title="LiveBench Methodology",
                body=html[:2000],
                item_type="methodology",
            )]
        return super().extract_items(html, page)

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        soup = BeautifulSoup(html, "lxml")
        entries: list[LeaderboardEntry] = []
        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 2:
                entries.append(LeaderboardEntry(
                    model=cells[0],
                    score=cells[1],
                    rank=len(entries) + 1,
                    variant="livebench",
                ))
        return entries
