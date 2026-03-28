"""Latency and cost threshold scorer."""

from __future__ import annotations

from ..base import BaseScorer, ScorerResult, register_scorer


class LatencyCostScorer(BaseScorer):
    """Score based on latency, cost, and token budget thresholds.

    Config:
        latency_threshold_ms: float | None — max acceptable latency
        cost_threshold_usd: float | None — max acceptable cost
        token_budget: int | None — max acceptable total tokens
    """

    scorer_type = "latency_cost"

    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        metadata = metadata or {}
        checks: dict[str, bool] = {}
        details: dict = {}

        latency_threshold = self.config.get("latency_threshold_ms")
        cost_threshold = self.config.get("cost_threshold_usd")
        token_budget = self.config.get("token_budget")

        latency = metadata.get("latency_ms", 0)
        cost = metadata.get("cost_estimate_usd", 0)
        tokens = metadata.get("total_tokens", 0)

        if latency_threshold is not None:
            checks["latency"] = latency <= latency_threshold
            details["latency_ms"] = latency
            details["latency_threshold_ms"] = latency_threshold

        if cost_threshold is not None:
            checks["cost"] = (cost or 0) <= cost_threshold
            details["cost_usd"] = cost
            details["cost_threshold_usd"] = cost_threshold

        if token_budget is not None:
            checks["tokens"] = (tokens or 0) <= token_budget
            details["total_tokens"] = tokens
            details["token_budget"] = token_budget

        if not checks:
            return ScorerResult(
                scorer_type=self.scorer_type,
                score=1.0,
                passed=True,
                details={"reason": "no thresholds configured"},
            )

        passed_count = sum(1 for v in checks.values() if v)
        score = passed_count / len(checks)
        all_passed = all(checks.values())

        details["checks"] = checks
        return ScorerResult(
            scorer_type=self.scorer_type,
            score=score,
            passed=all_passed,
            details=details,
        )


register_scorer("latency_cost", LatencyCostScorer)
