"""LMArena (Chatbot Arena) leaderboard collector."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from . import BenchmarkCollector, LeaderboardEntry

if TYPE_CHECKING:
    from ...config.settings import PageConfig


def _extract_model_name(td: Tag) -> str | None:
    """Extract clean model name from the Model cell's <a> tag."""
    link = td.select_one("a")
    if link:
        return link.get_text(strip=True) or None
    return td.get_text(strip=True) or None


def _extract_org(td: Tag) -> str | None:
    """Extract organization from the Model cell's secondary span."""
    spans = td.select("span")
    for span in spans:
        text = span.get_text(strip=True)
        if "·" in text:
            return text.split("·")[0].strip() or None
    return None


def _extract_elo(td: Tag) -> str | None:
    """Extract Elo score from the Score cell, stripping the ± confidence interval."""
    text = td.get_text(strip=True)
    if not text:
        return None
    # Score cell may contain "1504±6" — take the part before ±
    match = re.match(r"([\d,.]+)", text)
    return match.group(1).replace(",", "") if match else None


def _variant_from_url(url: str) -> str:
    """Derive arena variant from the page URL path."""
    path = urlparse(url).path.rstrip("/")
    # /leaderboard/text → arena_elo_text, /leaderboard → arena_elo
    if path.endswith("/leaderboard") or path == "":
        return "arena_elo"
    suffix = path.rsplit("/", 1)[-1]
    return f"arena_elo_{suffix}" if suffix != "leaderboard" else "arena_elo"


class LMArenaCollector(BenchmarkCollector):
    """Collector for LMArena human-preference arena leaderboard."""

    benchmark_family = "LMArena"

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        soup = BeautifulSoup(html, "lxml")
        variant = _variant_from_url(page.canonical_url)
        entries: list[LeaderboardEntry] = []

        for row in soup.select("tr"):
            tds = row.select("td")
            if len(tds) < 4:
                continue

            # Detect layout: 7+ columns = sub-page, 4-6 = main page
            if len(tds) >= 7:
                model_idx, score_idx = 2, 3
            else:
                model_idx, score_idx = 1, 2

            model_name = _extract_model_name(tds[model_idx])
            if not model_name:
                continue

            elo = _extract_elo(tds[score_idx])
            org = _extract_org(tds[model_idx])

            # Rank from first column
            rank_text = tds[0].get_text(strip=True)
            rank = int(rank_text) if rank_text.isdigit() else len(entries) + 1

            metadata: dict = {}
            if org:
                metadata["organization"] = org

            entries.append(
                LeaderboardEntry(
                    model=model_name,
                    score=elo or "N/A",
                    rank=rank,
                    variant=variant,
                    metadata=metadata,
                )
            )
        return entries
