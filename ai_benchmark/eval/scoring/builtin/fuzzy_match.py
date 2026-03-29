"""Fuzzy match scorer — SequenceMatcher-based text similarity."""

from __future__ import annotations

from difflib import SequenceMatcher

from ..base import BaseScorer, ScorerResult, register_scorer


class FuzzyMatchScorer(BaseScorer):
    """Score based on fuzzy text similarity using SequenceMatcher.

    Config:
        threshold: float — minimum similarity ratio to pass (default 0.85)
        case_sensitive: bool — whether comparison is case-sensitive (default False)
        strip_whitespace: bool — normalize whitespace before comparison (default True)
    """

    scorer_type = "fuzzy_match"

    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        if expected is None:
            return ScorerResult(
                scorer_type=self.scorer_type,
                score=0.0,
                passed=False,
                details={"error": "No expected output provided"},
            )

        threshold = self.config.get("threshold", 0.85)
        case_sensitive = self.config.get("case_sensitive", False)
        strip_ws = self.config.get("strip_whitespace", True)

        a = output
        b = expected

        if not case_sensitive:
            a = a.lower()
            b = b.lower()

        if strip_ws:
            a = " ".join(a.split())
            b = " ".join(b.split())

        ratio = SequenceMatcher(None, a, b).ratio()
        passed = ratio >= threshold

        return ScorerResult(
            scorer_type=self.scorer_type,
            score=ratio,
            passed=passed,
            details={
                "similarity": ratio,
                "threshold": threshold,
                "case_sensitive": case_sensitive,
            },
        )


register_scorer("fuzzy_match", FuzzyMatchScorer)
