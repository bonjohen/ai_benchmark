"""Humanity's Last Exam (HLE) benchmark collector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from . import BenchmarkCollector, LeaderboardEntry

if TYPE_CHECKING:
    from ...config.settings import PageConfig
    from ..base import RawItem  # noqa: TC004

# Column header substrings mapped to variant labels.
# The leaderboard exposes overall accuracy, text-only accuracy, and
# calibration score as separate columns.
_HLE_COLUMN_VARIANTS: list[tuple[str, str]] = [
    ("text only", "hle_text_only"),
    ("text-only", "hle_text_only"),
    ("calibration", "hle_calibration"),
    ("overall", "hle_public"),
    ("accuracy", "hle_public"),
]

_HLE_CONDITIONS = "2500 questions, automatic judging, confidence intervals"


def _detect_variant(header: str) -> str:
    """Map a column header to the appropriate HLE variant label."""
    lower = header.lower()
    for keyword, variant in _HLE_COLUMN_VARIANTS:
        if keyword in lower:
            return variant
    return "hle_public"


class HLECollector(BenchmarkCollector):
    """Collector for Scale AI's Humanity's Last Exam benchmark.

    Tracks public-question accuracy, text-only accuracy, and
    calibration metrics. Uses automatic judging with confidence intervals.

    Emits one LeaderboardEntry per score column per model so that
    text-only and calibration slices are tracked separately.
    """

    benchmark_family = "HLE"

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
        return super().extract_items(html, page)

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        soup = BeautifulSoup(html, "lxml")
        entries: list[LeaderboardEntry] = []

        # Detect column headers from the first <tr> with <th> cells
        headers: list[str] = []
        header_row = soup.select_one("tr:has(th)")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.select("th")]

        for row in soup.select("tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) < 2:
                continue
            model = cells[0]
            if not model:
                continue

            if headers and len(headers) >= len(cells):
                # Emit one entry per score column with the appropriate variant
                for col_idx, score in enumerate(cells[1:], start=1):
                    if not score:
                        continue
                    col_header = headers[col_idx] if col_idx < len(headers) else ""
                    variant = _detect_variant(col_header)
                    entries.append(
                        LeaderboardEntry(
                            model=model,
                            score=score,
                            rank=len(entries) + 1,
                            variant=variant,
                            conditions=_HLE_CONDITIONS,
                        )
                    )
            else:
                # Fallback: single entry with public variant
                entries.append(
                    LeaderboardEntry(
                        model=model,
                        score=cells[1],
                        rank=len(entries) + 1,
                        variant="hle_public",
                        conditions=_HLE_CONDITIONS,
                    )
                )

        return entries
