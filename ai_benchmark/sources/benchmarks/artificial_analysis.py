"""Artificial Analysis leaderboard collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from . import BenchmarkCollector, LeaderboardEntry
from ..base import RawItem


class ArtificialAnalysisCollector(BenchmarkCollector):
    """Collector for Artificial Analysis performance leaderboard."""

    benchmark_family = "Artificial Analysis"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "methodology" in page.page_type:
            return self._extract_methodology(html)
        return super().extract_items(html, page)

    def _extract_methodology(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("section, article, .content-block, p"):
            text = section.get_text(strip=True)
            if text and len(text) > 20:
                items.append(RawItem(
                    title=text[:200],
                    body=text,
                    item_type="methodology_description",
                ))
        return items

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
                    variant="performance",
                ))
        return entries
