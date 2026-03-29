"""End-to-end evaluation execution test.

Exercises the full orchestrator lifecycle: create_run -> execute_run -> score_run,
with a real exact_match scorer, verifying status transitions, item results,
aggregate metrics, and completed_items count.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.execution.adapters.base import GenerationResult
from ai_benchmark.eval.execution.orchestrator import RunOrchestrator
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401 — resolve mapper
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunItemResult
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Fixtures ──


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def seed_data_no_scorer(db_session: AsyncSession):
    """Seed data with scorer_config=[] (no scoring)."""
    ds = Dataset(name="e2e-ds-noscore", source="manual")
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
            input_text=f"What is {i} + 1?",
            expected_output=str(i + 1),
        )
        db_session.add(tc)
        cases.append(tc)
    await db_session.flush()

    ed = EvaluationDefinition(name="e2e-eval-noscore", execution_mode="sequential")
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
        name="e2e-target-noscore",
        model_name="test-model",
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


@pytest.fixture
async def seed_data_with_scorer(db_session: AsyncSession):
    """Seed data with a real exact_match scorer configured."""
    ds = Dataset(name="e2e-ds-scored", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=4)
    db_session.add(dv)
    await db_session.flush()

    # 4 test cases: the mock adapter will return the exact expected output for cases 0-2,
    # and a wrong answer for case 3
    test_data = [
        ("What is 1+1?", "2"),
        ("What is 2+2?", "4"),
        ("What is 3+3?", "6"),
        ("What is 5+5?", "10"),
    ]
    cases = []
    for i, (inp, exp) in enumerate(test_data):
        tc = TestCase(
            dataset_version_id=dv.id,
            item_index=i,
            input_text=inp,
            expected_output=exp,
        )
        db_session.add(tc)
        cases.append(tc)
    await db_session.flush()

    # Create scorer: exact_match
    scorer = Scorer(name="e2e-exact", scorer_type="exact_match")
    db_session.add(scorer)
    await db_session.flush()

    sv = ScorerVersion(
        scorer_id=scorer.id,
        version_number=1,
        config=json.dumps({"case_sensitive": False, "strip_whitespace": True}),
    )
    db_session.add(sv)
    await db_session.flush()

    ed = EvaluationDefinition(name="e2e-eval-scored", execution_mode="sequential")
    db_session.add(ed)
    await db_session.flush()

    scorer_config = [
        {"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5},
    ]
    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps(scorer_config),
    )
    db_session.add(ev)
    await db_session.flush()

    target = TargetConfiguration(
        name="e2e-target-scored",
        model_name="test-model-scored",
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
        "scorer": scorer,
        "scorer_version": sv,
    }


# ── Helpers ──


def _make_result(output_text: str) -> GenerationResult:
    return GenerationResult(
        output_text=output_text,
        latency_ms=42.0,
        prompt_tokens=8,
        completion_tokens=3,
        total_tokens=11,
    )


# ── Test class ──


class TestEndToEndEvalExecution:
    """End-to-end tests for the full create -> execute -> score lifecycle."""

    @pytest.mark.asyncio
    async def test_lifecycle_no_scorer(self, db_session: AsyncSession, seed_data_no_scorer):
        """Full lifecycle with scorer_config=[] skips scoring, still completes."""
        chain = seed_data_no_scorer
        orch = RunOrchestrator()

        # 1. create_run -> queued
        run = await orch.create_run(
            db_session,
            evaluation_version_id=chain["eval_version"].id,
            target_config_id=chain["target"].id,
        )
        assert run.status == "queued"
        assert run.total_items == 3
        assert run.completed_items == 0
        assert run.failed_items == 0

        # 2. execute_run -> running -> items processed
        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _make_result("mock answer")
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)

        # After execution: verify run counters
        assert run.completed_items == 3
        assert run.failed_items == 0

        # Verify status was set to running during execution
        # (it's still running at this point, score_run will finalize)

        # Verify RunItemResult records were created
        stmt = (
            select(RunItemResult)
            .where(RunItemResult.run_id == run.id)
            .order_by(RunItemResult.item_index)
        )
        result = await db_session.execute(stmt)
        items = list(result.scalars().all())
        assert len(items) == 3
        for i, item in enumerate(items):
            assert item.item_index == i
            assert item.raw_output == "mock answer"
            assert item.error_message is None
            assert item.latency_ms == 42.0
            assert item.total_tokens == 11

        # 3. score_run -> scoring -> completed
        run = await orch.score_run(db_session, run.id)
        assert run.status == "completed"

        # Even with no scorers, basic aggregates should be computed
        stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run.id)
        result = await db_session.execute(stmt)
        metrics = {m.metric_name: m.metric_value for m in result.scalars().all()}
        assert "avg_latency_ms" in metrics
        assert metrics["avg_latency_ms"] == pytest.approx(42.0)
        assert "total_tokens" in metrics
        assert metrics["total_tokens"] == pytest.approx(33.0)  # 11 * 3

    @pytest.mark.asyncio
    async def test_lifecycle_with_exact_match_scorer(
        self, db_session: AsyncSession, seed_data_with_scorer
    ):
        """Full lifecycle with exact_match scorer: 3 pass, 1 fail."""
        chain = seed_data_with_scorer
        orch = RunOrchestrator()

        # The adapter returns the correct answer for the first 3 items
        # and a wrong answer for the 4th
        expected_outputs = ["2", "4", "6", "wrong"]

        call_idx = 0

        async def _side_effect(prompt, params, opts=None):
            nonlocal call_idx
            output = expected_outputs[call_idx]
            call_idx += 1
            return _make_result(output)

        # 1. create
        run = await orch.create_run(
            db_session,
            evaluation_version_id=chain["eval_version"].id,
            target_config_id=chain["target"].id,
        )
        assert run.status == "queued"
        assert run.total_items == 4

        # 2. execute
        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.side_effect = _side_effect
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)

        assert run.completed_items == 4
        assert run.failed_items == 0  # all generated successfully (no adapter errors)

        # 3. score
        run = await orch.score_run(db_session, run.id)
        assert run.status == "completed"

        # Verify item-level scoring results
        stmt = (
            select(RunItemResult)
            .where(RunItemResult.run_id == run.id)
            .order_by(RunItemResult.item_index)
        )
        result = await db_session.execute(stmt)
        items = list(result.scalars().all())
        assert len(items) == 4

        # Items 0-2 match expected -> pass; item 3 "wrong" != "10" -> fail
        assert items[0].overall_pass is True
        assert items[1].overall_pass is True
        assert items[2].overall_pass is True
        assert items[3].overall_pass is False

        # Verify scorer_results JSON was populated
        for item in items:
            sr = json.loads(item.scorer_results)
            assert len(sr) == 1
            assert sr[0]["scorer_type"] == "exact_match"
            assert "score" in sr[0]

        # Verify aggregate metrics include pass_rate
        stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run.id)
        result = await db_session.execute(stmt)
        metrics = {m.metric_name: m.metric_value for m in result.scalars().all()}

        assert "pass_rate" in metrics
        assert metrics["pass_rate"] == pytest.approx(0.75)  # 3 out of 4
        assert "scorer_exact_match_pass_rate" in metrics
        assert metrics["scorer_exact_match_pass_rate"] == pytest.approx(0.75)
        assert "avg_latency_ms" in metrics

    @pytest.mark.asyncio
    async def test_status_transitions(self, db_session: AsyncSession, seed_data_no_scorer):
        """Verify the run transitions through queued -> running -> scoring -> completed."""
        chain = seed_data_no_scorer
        orch = RunOrchestrator()

        run = await orch.create_run(
            db_session,
            evaluation_version_id=chain["eval_version"].id,
            target_config_id=chain["target"].id,
        )

        # After create: queued
        fresh = await db_session.get(Run, run.id)
        assert fresh.status == "queued"

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _make_result("answer")
            mock_resolve.return_value = mock_adapter

            # After execute: status was set to "running" internally
            run = await orch.execute_run(db_session, run.id)
            # The run is still in "running" state after execute_run returns
            fresh = await db_session.get(Run, run.id)
            assert fresh.status == "running"

            # After score: transitions through scoring -> completed
            run = await orch.score_run(db_session, run.id)
            fresh = await db_session.get(Run, run.id)
            assert fresh.status == "completed"

        # Verify timestamps were set
        assert fresh.started_at is not None
        assert fresh.completed_at is not None

    @pytest.mark.asyncio
    async def test_partial_failure_e2e(self, db_session: AsyncSession, seed_data_no_scorer):
        """When some adapter calls fail, run ends as partially_completed."""
        chain = seed_data_no_scorer
        settings = EvalSettings(retry_failed_items=0)
        orch = RunOrchestrator(settings=settings)

        run = await orch.create_run(
            db_session,
            evaluation_version_id=chain["eval_version"].id,
            target_config_id=chain["target"].id,
        )

        call_count = 0

        async def _side_effect(prompt, params, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return GenerationResult(
                    output_text="",
                    latency_ms=100.0,
                    error="Connection refused",
                )
            return _make_result("ok")

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.side_effect = _side_effect
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)

        assert run.completed_items == 2
        assert run.failed_items == 1

        run = await orch.score_run(db_session, run.id)
        assert run.status == "partially_completed"

        # Verify item results: 3 records total, 1 with error
        stmt = select(RunItemResult).where(RunItemResult.run_id == run.id)
        result = await db_session.execute(stmt)
        items = list(result.scalars().all())
        assert len(items) == 3
        error_items = [i for i in items if i.error_message]
        assert len(error_items) == 1
        assert "Connection refused" in error_items[0].error_message

    @pytest.mark.asyncio
    async def test_completed_items_count_matches_results(
        self, db_session: AsyncSession, seed_data_no_scorer
    ):
        """Verify run.completed_items matches the actual RunItemResult count."""
        chain = seed_data_no_scorer
        orch = RunOrchestrator()

        run = await orch.create_run(
            db_session,
            evaluation_version_id=chain["eval_version"].id,
            target_config_id=chain["target"].id,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = _make_result("answer")
            mock_resolve.return_value = mock_adapter

            run = await orch.execute_run(db_session, run.id)

        # Count actual item results
        stmt = select(RunItemResult).where(
            RunItemResult.run_id == run.id,
            RunItemResult.error_message.is_(None),
        )
        result = await db_session.execute(stmt)
        success_items = list(result.scalars().all())

        assert run.completed_items == len(success_items)
        assert run.completed_items == 3
        assert run.total_items == 3
