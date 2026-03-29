"""Scorer runner — dispatches scorers for each RunItemResult and computes aggregates."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..models.evaluation import EvaluationVersion
from ..models.run import Run, RunAggregateMetric, RunItemResult
from ..models.scorer import Scorer, ScorerVersion
from .base import resolve_scorer

# Ensure all built-in scorers are registered
from .builtin import (  # noqa: F401
    exact_match,
    format_validator,
    latency_cost,
    model_judge,
    rubric,
    safety,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ScorerRunner:
    """Dispatches configured scorers against each item result."""

    async def score_run(self, session: AsyncSession, run_id: int) -> None:
        """Score all item results for a run using its evaluation's scorer config."""
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")

        ev = await session.get(EvaluationVersion, run.evaluation_version_id)
        if ev is None:
            raise ValueError(f"EvaluationVersion {run.evaluation_version_id} not found")

        scorer_config = json.loads(ev.scorer_config) if ev.scorer_config else []
        if not scorer_config:
            logger.info("no_scorers_configured", run_id=run_id)
            return

        # Load scorer versions and resolve scorer instances
        scorers: list[tuple[dict, ScorerVersion, Scorer]] = []
        for sc in scorer_config:
            sv_id = sc.get("scorer_version_id")
            sv = await session.get(ScorerVersion, sv_id)
            if sv is None:
                logger.warning("scorer_version_not_found", id=sv_id)
                continue
            scorer_obj = await session.get(Scorer, sv.scorer_id)
            if scorer_obj is None:
                logger.warning("scorer_not_found", id=sv.scorer_id)
                continue
            scorers.append((sc, sv, scorer_obj))

        # Load all item results
        stmt = (
            select(RunItemResult)
            .where(RunItemResult.run_id == run_id)
            .order_by(RunItemResult.item_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        # Score each item
        for item in items:
            # Load the test case for expected output
            from ..models.dataset import TestCase

            test_case = await session.get(TestCase, item.test_case_id)

            item_scorer_results: list[dict] = []
            weighted_pass_sum = 0.0
            total_weight = 0.0

            for sc_conf, sv, scorer_obj in scorers:
                weight = sc_conf.get("weight", 1.0)
                pass_threshold = sc_conf.get("pass_threshold", 0.5)
                config = json.loads(sv.config) if sv.config else {}

                scorer = resolve_scorer(scorer_obj.scorer_type, config)

                # Build metadata for latency/cost scorer
                item_metadata = {
                    "latency_ms": item.latency_ms or 0,
                    "cost_estimate_usd": item.cost_estimate_usd or 0,
                    "total_tokens": item.total_tokens or 0,
                    "prompt_tokens": item.prompt_tokens or 0,
                    "completion_tokens": item.completion_tokens or 0,
                }

                scorer_result = await scorer.score(
                    output=item.raw_output or "",
                    expected=test_case.expected_output if test_case else None,
                    input_text=test_case.input_text if test_case else None,
                    context=test_case.context if test_case else None,
                    metadata=item_metadata,
                )

                item_passed = scorer_result.score >= pass_threshold
                item_scorer_results.append(
                    {
                        "scorer_version_id": sv.id,
                        "scorer_type": scorer_result.scorer_type,
                        "score": scorer_result.score,
                        "passed": item_passed,
                        "weight": weight,
                        "details": scorer_result.details,
                    }
                )

                weighted_pass_sum += weight * (1.0 if item_passed else 0.0)
                total_weight += weight

            item.scorer_results = json.dumps(item_scorer_results)
            overall = (weighted_pass_sum / total_weight >= 0.5) if total_weight > 0 else None
            item.overall_pass = overall

        await session.flush()

    async def compute_aggregates(self, session: AsyncSession, run_id: int) -> None:
        """Compute aggregate metrics for a scored run."""
        stmt = select(RunItemResult).where(RunItemResult.run_id == run_id)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return

        # Overall pass rate
        scored_items = [i for i in items if i.overall_pass is not None]
        if scored_items:
            pass_rate = sum(1 for i in scored_items if i.overall_pass) / len(scored_items)
            await self._upsert_metric(session, run_id, "pass_rate", pass_rate)

        # Latency stats
        latencies = sorted(i.latency_ms for i in items if i.latency_ms)
        if latencies:
            await self._upsert_metric(
                session, run_id, "avg_latency_ms", sum(latencies) / len(latencies)
            )
            await self._upsert_metric(
                session, run_id, "p50_latency_ms", latencies[len(latencies) // 2]
            )
            if len(latencies) >= 20:
                await self._upsert_metric(
                    session, run_id, "p95_latency_ms", latencies[int(len(latencies) * 0.95)]
                )
                await self._upsert_metric(
                    session, run_id, "p99_latency_ms", latencies[int(len(latencies) * 0.99)]
                )

        # Token stats
        tokens = [i.total_tokens for i in items if i.total_tokens]
        if tokens:
            await self._upsert_metric(session, run_id, "avg_tokens", sum(tokens) / len(tokens))
            await self._upsert_metric(session, run_id, "total_tokens", sum(tokens))

        # Cost stats
        costs = [i.cost_estimate_usd for i in items if i.cost_estimate_usd]
        if costs:
            await self._upsert_metric(session, run_id, "total_cost_usd", sum(costs))

        # Per-scorer pass rates
        scorer_accum: dict[str, list[bool]] = {}
        for item in items:
            try:
                scorer_results = json.loads(item.scorer_results) if item.scorer_results else []
            except json.JSONDecodeError:
                continue
            for sr in scorer_results:
                stype = sr.get("scorer_type", "unknown")
                metric_key = f"scorer_{stype}_pass_rate"
                scorer_accum.setdefault(metric_key, []).append(sr.get("passed", False))

        if scorer_accum:
            for metric_key, passes in scorer_accum.items():
                rate = sum(1 for p in passes if p) / len(passes)
                await self._upsert_metric(session, run_id, metric_key, rate)

        await session.flush()

    async def _upsert_metric(
        self, session: AsyncSession, run_id: int, name: str, value: float
    ) -> None:
        stmt = select(RunAggregateMetric).where(
            RunAggregateMetric.run_id == run_id,
            RunAggregateMetric.metric_name == name,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.metric_value = value
        else:
            session.add(RunAggregateMetric(run_id=run_id, metric_name=name, metric_value=value))
