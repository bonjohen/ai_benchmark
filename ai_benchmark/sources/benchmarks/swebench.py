"""SWE-bench leaderboard collector with variant awareness."""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import BenchmarkCollector, LeaderboardEntry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...config.settings import PageConfig

# Known SWE-bench variants
SWEBENCH_VARIANTS = {"verified", "lite", "full", "pro", "multilingual", "multimodal"}


class SWEBenchCollector(BenchmarkCollector):
    """Collector for SWE-bench coding benchmark.

    Variant-aware: distinguishes between Verified, Lite, Full, Pro,
    Multilingual, and Multimodal subsets. Frontier contamination on
    public subsets is a documented concern.
    """

    benchmark_family = "SWE-bench"

    def _detect_variant(self, page: PageConfig) -> str:
        url_lower = page.canonical_url.lower()
        for variant in SWEBENCH_VARIANTS:
            if variant in url_lower:
                return variant
        return "unknown"

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        variant = self._detect_variant(page)
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
                        variant=variant,
                        conditions=(
                            f"SWE-bench {variant}; contamination risk noted for public subsets"
                        ),
                    )
                )
        return entries
