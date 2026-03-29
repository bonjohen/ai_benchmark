"""Terminal-Bench collector with registry/version tracking."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ...config.settings import PageConfig
from ..base import RawItem
from . import BenchmarkCollector, LeaderboardEntry


class TerminalBenchCollector(BenchmarkCollector):
    """Collector for Terminal-Bench terminal-environment agent benchmark."""

    benchmark_family = "Terminal-Bench"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "registry" in page.page_type:
            return self._extract_registry(html)
        return super().extract_items(html, page)

    def _extract_registry(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("section, h2, h3, li, tr"):
            text = section.get_text(strip=True)
            if text and len(text) > 10:
                items.append(
                    RawItem(
                        title=text[:200],
                        body=text,
                        item_type="registry_entry",
                    )
                )
        return items

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
                        variant="terminal_bench",
                    )
                )
        return entries
