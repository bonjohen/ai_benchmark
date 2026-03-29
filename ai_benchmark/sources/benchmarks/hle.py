"""Humanity's Last Exam (HLE) benchmark collector."""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import BenchmarkCollector, LeaderboardEntry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...config.settings import PageConfig


class HLECollector(BenchmarkCollector):
    """Collector for Scale AI's Humanity's Last Exam benchmark.

    Tracks public-question accuracy, text-only accuracy, and
    calibration metrics. Uses automatic judging with confidence intervals.
    """

    benchmark_family = "HLE"

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
                        variant="hle_public",
                        conditions="2500 questions, automatic judging, confidence intervals",
                    )
                )
        return entries
