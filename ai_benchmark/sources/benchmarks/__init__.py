"""Benchmark collectors with variant-aware extraction."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...config.settings import PageConfig
from ..base import RawItem, SourceCollector


@dataclass
class LeaderboardEntry:
    """A single entry from a benchmark leaderboard."""

    model: str
    score: float | str
    rank: int | None = None
    variant: str | None = None
    conditions: str | None = None
    metadata: dict = field(default_factory=dict)


class BenchmarkCollector(SourceCollector):
    """Base class for benchmark collectors with variant-aware extraction.

    Subclasses implement `extract_leaderboard()` to parse leaderboard data
    into structured entries, in addition to `extract_items()` for raw items.
    """

    benchmark_family: str = ""

    def extract_leaderboard(self, html: str, page: PageConfig) -> list[LeaderboardEntry]:
        """Extract structured leaderboard entries. Override in subclasses."""
        return []

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        """Default: convert leaderboard entries to RawItems."""
        entries = self.extract_leaderboard(html, page)
        items: list[RawItem] = []
        for entry in entries:
            items.append(RawItem(
                title=f"{self.benchmark_family}: {entry.model} = {entry.score}",
                body=f"Rank: {entry.rank}, Variant: {entry.variant}, Conditions: {entry.conditions}",
                item_type="benchmark_entry",
                model_hint=entry.model,
                metadata={
                    "score": entry.score,
                    "rank": entry.rank,
                    "variant": entry.variant,
                    "benchmark_variant": entry.variant,
                    "evaluation_conditions": entry.conditions,
                },
            ))
        return items
