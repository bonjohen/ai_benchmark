"""GAIA benchmark collector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from ..base import RawItem
from . import BenchmarkCollector, LeaderboardEntry

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class GAIACollector(BenchmarkCollector):
    """Collector for GAIA general AI assistant benchmark on Hugging Face."""

    benchmark_family = "GAIA"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "org" in page.page_type:
            return self._extract_org_page(html)
        return super().extract_items(html, page)

    def _extract_org_page(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for link in soup.select("a[href]"):
            text = link.get_text(strip=True)
            href = str(link.get("href", ""))
            if text and (
                "result" in text.lower()
                or "dataset" in text.lower()
                or "leaderboard" in text.lower()
            ):
                items.append(
                    RawItem(
                        title=text,
                        url=href,
                        item_type="gaia_artifact",
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
                        variant="gaia",
                    )
                )
        return entries
