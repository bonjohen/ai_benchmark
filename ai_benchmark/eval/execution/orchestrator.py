"""Run orchestrator — coordinates the full lifecycle of an evaluation run."""

from __future__ import annotations

import asyncio
import json

import structlog
from sqlalchemy import select

from ..config import EvalSettings
from ..models.dataset import TestCase
from ..models.evaluation import EvaluationVersion
from ..models.run import Run, RunAggregateMetric
from ..models.target import TargetConfiguration
from ..services import run_service
from .executor import ItemExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class RunOrchestrator:
    """Three-stage run lifecycle: create → execute → score → finalize."""

    def __init__(self, settings: EvalSettings | None = None):
        self.settings = settings or EvalSettings()

    async def create_run(
        self,
        session: AsyncSession,
        *,
        evaluation_version_id: int,
        target_config_id: int,
        trigger_type: str = "manual",
        priority: int = 0,
        machine_profile_id: int | None = None,
        run_group_id: int | None = None,
    ) -> Run:
        """Validate references, capture snapshot, create queued run."""
        ev = await session.get(EvaluationVersion, evaluation_version_id)
        if ev is None:
            raise ValueError(f"EvaluationVersion {evaluation_version_id} not found")

        tc = await session.get(TargetConfiguration, target_config_id)
        if tc is None:
            raise ValueError(f"TargetConfiguration {target_config_id} not found")

        # Count items in the dataset version
        item_count_stmt = select(TestCase.id).where(
            TestCase.dataset_version_id == ev.dataset_version_id
        )
        result = await session.execute(item_count_stmt)
        total_items = len(result.all())

        run = await run_service.create_run(
            session,
            evaluation_version_id=evaluation_version_id,
            target_config_id=target_config_id,
            dataset_version_id=ev.dataset_version_id,
            trigger_type=trigger_type,
            priority=priority,
            total_items=total_items,
            machine_profile_id=machine_profile_id,
            run_group_id=run_group_id,
        )
        logger.info("run_created", run_id=run.id, total_items=total_items)
        return run

    async def execute_run(self, session: AsyncSession, run_id: int) -> Run:
        """Load items, iterate through executor, update counters."""
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")

        await run_service.update_status(session, run_id, "running")

        ev = await session.get(EvaluationVersion, run.evaluation_version_id)
        tc = await session.get(TargetConfiguration, run.target_config_id)

        # Load test cases
        stmt = (
            select(TestCase)
            .where(TestCase.dataset_version_id == run.dataset_version_id)
            .order_by(TestCase.item_index)
        )
        result = await session.execute(stmt)
        test_cases = list(result.scalars().all())

        # Build executor from target config
        inference_params = json.loads(tc.inference_params) if tc.inference_params else {}
        runtime_options = json.loads(tc.runtime_options) if tc.runtime_options else {}

        executor = ItemExecutor(
            provider=tc.provider,
            endpoint_url=tc.endpoint_url,
            model_name=tc.model_name,
            api_key=runtime_options.pop("api_key", None),
            inference_params=inference_params,
            runtime_options=runtime_options,
            prompt_template=ev.prompt_template,
            prompt_wrapper=tc.prompt_wrapper,
            item_timeout=self.settings.item_timeout_seconds,
            max_retries=self.settings.retry_failed_items,
        )

        # Determine execution mode
        eval_def = (
            await session.get(ev.evaluation.__class__, ev.evaluation_id)
            if ev.evaluation_id
            else None
        )
        execution_mode = (
            eval_def.execution_mode if eval_def else self.settings.default_execution_mode
        )

        if execution_mode == "parallel":
            await self._execute_parallel(session, run, executor, test_cases)
        else:
            await self._execute_sequential(session, run, executor, test_cases)

        # Refresh run to get updated counters
        await session.refresh(run)
        return run

    async def _execute_sequential(
        self,
        session: AsyncSession,
        run: Run,
        executor: ItemExecutor,
        test_cases: list[TestCase],
    ) -> None:
        for idx, tc in enumerate(test_cases):
            try:
                item_result = await executor.execute_item(session, run.id, tc, idx)
                if item_result.error_message:
                    run.failed_items += 1
                else:
                    run.completed_items += 1
            except Exception as e:
                logger.error("item_execution_error", run_id=run.id, index=idx, error=str(e))
                run.failed_items += 1
            await session.flush()

    async def _execute_parallel(
        self,
        session: AsyncSession,
        run: Run,
        executor: ItemExecutor,
        test_cases: list[TestCase],
    ) -> None:
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_items)

        async def _run_item(idx: int, tc: TestCase) -> None:
            async with semaphore:
                try:
                    item_result = await executor.execute_item(session, run.id, tc, idx)
                    if item_result.error_message:
                        run.failed_items += 1
                    else:
                        run.completed_items += 1
                except Exception as e:
                    logger.error("item_execution_error", run_id=run.id, index=idx, error=str(e))
                    run.failed_items += 1

        tasks = [_run_item(idx, tc) for idx, tc in enumerate(test_cases)]
        await asyncio.gather(*tasks)
        await session.flush()

    async def score_run(self, session: AsyncSession, run_id: int) -> Run:
        """Set status=scoring, invoke scorer runner, compute aggregates."""
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")

        await run_service.update_status(session, run_id, "scoring")

        from ..scoring.scorer_runner import ScorerRunner

        runner = ScorerRunner()
        await runner.score_run(session, run_id)
        await runner.compute_aggregates(session, run_id)

        return await self.finalize_run(session, run_id)

    async def _compute_basic_aggregates(self, session: AsyncSession, run_id: int) -> None:
        """Compute basic latency/token/cost aggregates from item results."""
        from ..models.run import RunItemResult

        stmt = select(RunItemResult).where(RunItemResult.run_id == run_id)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return

        latencies = [i.latency_ms for i in items if i.latency_ms]
        tokens = [i.total_tokens for i in items if i.total_tokens]
        costs = [i.cost_estimate_usd for i in items if i.cost_estimate_usd]

        metrics: list[tuple[str, float]] = []
        if latencies:
            latencies.sort()
            metrics.append(("avg_latency_ms", sum(latencies) / len(latencies)))
            metrics.append(("p50_latency_ms", latencies[len(latencies) // 2]))
            if len(latencies) >= 20:
                metrics.append(("p95_latency_ms", latencies[int(len(latencies) * 0.95)]))
                metrics.append(("p99_latency_ms", latencies[int(len(latencies) * 0.99)]))
        if tokens:
            metrics.append(("avg_tokens", sum(tokens) / len(tokens)))
            metrics.append(("total_tokens", sum(tokens)))
        if costs:
            metrics.append(("total_cost_usd", sum(costs)))

        passed = sum(1 for i in items if i.overall_pass is True)
        total_scored = sum(1 for i in items if i.overall_pass is not None)
        if total_scored:
            metrics.append(("pass_rate", passed / total_scored))

        for name, value in metrics:
            metric = RunAggregateMetric(
                run_id=run_id,
                metric_name=name,
                metric_value=value,
            )
            session.add(metric)
        await session.flush()

    async def finalize_run(self, session: AsyncSession, run_id: int) -> Run:
        """Set terminal status based on item outcomes."""
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")

        if run.failed_items == 0:
            terminal = "completed"
        elif run.completed_items == 0:
            terminal = "failed"
        else:
            terminal = "partially_completed"

        await run_service.update_status(session, run_id, terminal)
        logger.info(
            "run_finalized",
            run_id=run_id,
            status=terminal,
            completed=run.completed_items,
            failed=run.failed_items,
        )
        await session.refresh(run)
        return run
