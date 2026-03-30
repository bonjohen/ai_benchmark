"""Terminal-Bench collector with registry/version tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from ..base import RawItem, extract_title
from . import BenchmarkCollector, LeaderboardEntry

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class TerminalBenchCollector(BenchmarkCollector):
    """Collector for Terminal-Bench terminal-environment agent benchmark."""

    benchmark_family = "Terminal-Bench"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
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
                        title=extract_title(text),
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
