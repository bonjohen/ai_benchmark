"""Exact match and fuzzy match scorers."""

from __future__ import annotations

import difflib
import unicodedata

from ..base import BaseScorer, ScorerResult, register_scorer


class ExactMatchScorer(BaseScorer):
    """Score 1.0 if output matches expected exactly (configurable normalization)."""

    scorer_type = "exact_match"

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
                details={"reason": "no expected output"},
            )

        a, b = output, expected

        if self.config.get("strip_whitespace", True):
            a, b = a.strip(), b.strip()

        if self.config.get("normalize_unicode", False):
            a = unicodedata.normalize("NFC", a)
            b = unicodedata.normalize("NFC", b)

        if not self.config.get("case_sensitive", True):
            a, b = a.lower(), b.lower()

        matched = a == b
        return ScorerResult(
            scorer_type=self.scorer_type,
            score=1.0 if matched else 0.0,
            passed=matched,
            details={"case_sensitive": self.config.get("case_sensitive", True)},
        )


class FuzzyMatchScorer(BaseScorer):
    """Score based on similarity between output and expected."""

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
                details={"reason": "no expected output"},
            )

        threshold = self.config.get("threshold", 0.85)
        method = self.config.get("method", "levenshtein")

        if method == "token_overlap":
            out_tokens = set(output.lower().split())
            exp_tokens = set(expected.lower().split())
            ratio = 0.0 if not exp_tokens else len(out_tokens & exp_tokens) / len(exp_tokens)
        else:
            # Default: SequenceMatcher (Levenshtein-like)
            ratio = difflib.SequenceMatcher(None, output, expected).ratio()

        return ScorerResult(
            scorer_type=self.scorer_type,
            score=ratio,
            passed=ratio >= threshold,
            details={"method": method, "threshold": threshold, "similarity": ratio},
        )


register_scorer("exact_match", ExactMatchScorer)
register_scorer("fuzzy_match", FuzzyMatchScorer)
