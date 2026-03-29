"""Tests for RunOrchestrator — full run lifecycle, partial failure, matrix runs."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.execution.adapters.base import GenerationResult
from ai_benchmark.eval.execution.orchestrator import RunOrchestrator
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401 — resolve mapper
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import RunAggregateMetric
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.models.base import create_session_factory

# ── Fixtures ──


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def full_chain(db_session):
    """Build dataset + eval + target chain for orchestrator tests."""
    ds = Dataset(name="orch-ds", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=3)
    db_session.add(dv)
    await db_session.flush()

    cases = []
    for i in range(3):
        tc = TestCase(
            dataset_version_id=dv.id,
            item_index=i,
            input_text=f"Q{i}",
            expected_output=f"A{i}",
        )
        db_session.add(tc)
        cases.append(tc)
    await db_session.flush()

    ed = EvaluationDefinition(name="orch-eval", execution_mode="sequential")
    db_session.add(ed)
    await db_session.flush()

    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([]),
    )
    db_session.add(ev)
    await db_session.flush()

    target = TargetConfiguration(
        name="orch-target",
        model_name="gpt-4o",
        provider="openai",
        inference_params=json.dumps({"temperature": 0.0}),
    )
    db_session.add(target)
    await db_session.flush()

    return {
        "dataset": ds,
        "version": dv,
        "cases": cases,
        "eval_def": ed,
        "eval_version": ev,
        "target": target,
    }


def _mock_generate_success():
    """Return a successful GenerationResult."""
    return GenerationResult(
        output_text="mock answer",
        latency_ms=50.0,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )


def _mock_generate_error():
    """Return an error GenerationResult."""
    return GenerationResult(
        output_text="",
        latency_ms=100.0,
        error="Connection refused",
    )


# ── Tests ──


class TestCreateRun:
    @pytest.mark.asyncio
    async def test_create_run_sets_queued(self, db_session, full_chain):
        orch = RunOrchestrator()
        run = await orch.create_run(
            db_session,
            evaluation_version_id=full_chain["eval_version"].id,
            target_config_id=full_chain["target"].id,
        )
        assert run.status == "queued"
        assert run.total_items == 3

    @pytest.mark.asyncio
    async def test_create_run_invalid_eval_version(self, db_session, full_chain):
        orch = RunOrchestrator()
        with pytest.raises(ValueError, match="EvaluationVersion 9999 not found"):
            await orch.create_run(
                db_session,
                evaluation_version_id=9999,
                target_config_id=full_chain["target"].id,
            )

    @pytest.mark.asyncio
    async def test_create_run_invalid_target(self, db_session, full_chain):
        orch = RunOrchestrator()
        with pytest.raises(ValueError, match="TargetConfiguration 9999 not found"):
            await orch.create_run(
                db_session,
                evaluation_version_id=full_chain["eval_version"].id,
                target_config_id=9999,
            )


class TestExecuteRun:
    @pytest.mark.asyncio
    async def test_full_success_lifecycle(self, db_session, full_chain):
        """All items succeed → status=completed."""
        orch = RunOrchestrator()
        run = await orch.create_run(
            db_session,
            evaluation_version_id=full_chain["eval_version"].id,
            target_config_id=full_chain["target"].id,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _mock_generate_success()
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)
            assert run.completed_items == 3
            assert run.failed_items == 0

            run = await orch.score_run(db_session, run.id)
            assert run.status == "completed"

    @pytest.mark.asyncio
    async def test_partial_failure(self, db_session, full_chain):
        """Some items fail → status=partially_completed."""
        settings = EvalSettings(retry_failed_items=0)
        orch = RunOrchestrator(settings=settings)
        run = await orch.create_run(
            db_session,
            evaluation_version_id=full_chain["eval_version"].id,
            target_config_id=full_chain["target"].id,
        )

        call_count = 0

        async def _side_effect(prompt, params, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return _mock_generate_error()
            return _mock_generate_success()

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.side_effect = _side_effect
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)
            # 2 succeeded, 1 failed (the one that errored still counts as
            # "completed" from executor POV since error is captured in result,
            # but the orchestrator counts error_message items as failed)
            assert run.completed_items == 2
            assert run.failed_items == 1

            run = await orch.finalize_run(db_session, run.id)
            assert run.status == "partially_completed"

    @pytest.mark.asyncio
    async def test_all_items_fail(self, db_session, full_chain):
        """All items fail → status=failed."""
        orch = RunOrchestrator()
        run = await orch.create_run(
            db_session,
            evaluation_version_id=full_chain["eval_version"].id,
            target_config_id=full_chain["target"].id,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _mock_generate_error()
            mock_resolve.return_value = mock_adapter

            # max_retries=0 so it doesn't retry on the error
            settings = EvalSettings(retry_failed_items=0)
            orch = RunOrchestrator(settings=settings)
            run = await orch.execute_run(db_session, run.id)
            run = await orch.finalize_run(db_session, run.id)
            assert run.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_run(self, db_session):
        orch = RunOrchestrator()
        with pytest.raises(ValueError, match="Run 9999 not found"):
            await orch.execute_run(db_session, 9999)


class TestAggregateMetrics:
    @pytest.mark.asyncio
    async def test_basic_aggregates_computed(self, db_session, full_chain):
        """score_run computes latency/token aggregates."""
        orch = RunOrchestrator()
        run = await orch.create_run(
            db_session,
            evaluation_version_id=full_chain["eval_version"].id,
            target_config_id=full_chain["target"].id,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _mock_generate_success()
            mock_resolve.return_value = mock_adapter

            await orch.execute_run(db_session, run.id)
            run = await orch.score_run(db_session, run.id)

            from sqlalchemy import select

            stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run.id)
            result = await db_session.execute(stmt)
            metrics = {m.metric_name: m.metric_value for m in result.scalars().all()}

            assert "avg_latency_ms" in metrics
            assert metrics["avg_latency_ms"] == pytest.approx(50.0)
            assert "total_tokens" in metrics
            assert metrics["total_tokens"] == 45  # 15 * 3


class TestEvalSettings:
    def test_defaults(self):
        settings = EvalSettings()
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 8100
        assert settings.max_concurrent_items == 5
        assert settings.default_execution_mode == "sequential"
        assert settings.item_timeout_seconds == 120
        assert settings.retry_failed_items == 2
        assert settings.enable_cost_tracking is True
        assert settings.local_only_mode is False
