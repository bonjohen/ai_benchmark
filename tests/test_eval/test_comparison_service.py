"""Tests for comparison service — multi-run comparison and config diff."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.machine import MachineProfile, MachineSnapshot
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunItemResult
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.eval.services import comparison_service
from ai_benchmark.models.base import create_session_factory


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


async def _setup_two_runs(session: AsyncSession):
    """Create a full chain and two completed runs with metrics and item results."""
    ds = Dataset(name="cmp-ds")
    session.add(ds)
    await session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
    session.add(dv)
    await session.flush()

    tc1 = TestCase(dataset_version_id=dv.id, item_index=0, input_text="q1", expected_output="a1")
    tc2 = TestCase(dataset_version_id=dv.id, item_index=1, input_text="q2", expected_output="a2")
    session.add_all([tc1, tc2])
    await session.flush()

    scorer = Scorer(name="exact", scorer_type="exact_match")
    session.add(scorer)
    await session.flush()
    sv = ScorerVersion(scorer_id=scorer.id, version_number=1, config="{}")
    session.add(sv)
    await session.flush()

    ed = EvaluationDefinition(name="cmp-eval", execution_mode="sequential")
    session.add(ed)
    await session.flush()
    ev = EvaluationVersion(
        evaluation_id=ed.id, version_number=1,
        dataset_version_id=dv.id, scorer_config="[]",
    )
    session.add(ev)
    await session.flush()

    # Two targets with different temperatures
    t1 = TargetConfiguration(
        name="gpt-4o-temp0",
        model_name="gpt-4o",
        provider="openai",
        inference_params=json.dumps({"temperature": 0.0}),
    )
    t2 = TargetConfiguration(
        name="gpt-4o-temp1",
        model_name="gpt-4o",
        provider="openai",
        inference_params=json.dumps({"temperature": 1.0}),
    )
    session.add_all([t1, t2])
    await session.flush()

    # Two runs
    run1 = Run(
        evaluation_version_id=ev.id, target_config_id=t1.id,
        dataset_version_id=dv.id, status="completed", total_items=2,
    )
    run2 = Run(
        evaluation_version_id=ev.id, target_config_id=t2.id,
        dataset_version_id=dv.id, status="completed", total_items=2,
    )
    session.add_all([run1, run2])
    await session.flush()

    # Item results for run1 (both pass)
    for tc, output, passed in [(tc1, "a1", True), (tc2, "a2", True)]:
        session.add(RunItemResult(
            run_id=run1.id, test_case_id=tc.id, item_index=tc.item_index,
            input_sent=tc.input_text, raw_output=output,
            scorer_results="[]", overall_pass=passed,
        ))

    # Item results for run2 (one pass, one fail)
    session.add(RunItemResult(
        run_id=run2.id, test_case_id=tc1.id, item_index=0,
        input_sent="q1", raw_output="a1",
        scorer_results="[]", overall_pass=True,
    ))
    session.add(RunItemResult(
        run_id=run2.id, test_case_id=tc2.id, item_index=1,
        input_sent="q2", raw_output="wrong",
        scorer_results="[]", overall_pass=False,
    ))
    await session.flush()

    # Aggregate metrics
    session.add(RunAggregateMetric(run_id=run1.id, metric_name="overall_accuracy", metric_value=1.0))
    session.add(RunAggregateMetric(run_id=run1.id, metric_name="avg_latency_ms", metric_value=100.0))
    session.add(RunAggregateMetric(run_id=run2.id, metric_name="overall_accuracy", metric_value=0.5))
    session.add(RunAggregateMetric(run_id=run2.id, metric_name="avg_latency_ms", metric_value=80.0))
    await session.flush()

    return run1, run2, t1, t2


async def test_compare_two_runs_metric_deltas(db_session: AsyncSession):
    run1, run2, _, _ = await _setup_two_runs(db_session)
    result = await comparison_service.compare_runs(db_session, [run1.id, run2.id])

    assert result["run_ids"] == [run1.id, run2.id]
    metrics = {m["metric"]: m for m in result["metric_comparison"]}
    assert "overall_accuracy" in metrics
    assert metrics["overall_accuracy"][f"run_{run1.id}"] == 1.0
    assert metrics["overall_accuracy"][f"run_{run2.id}"] == 0.5
    assert metrics["overall_accuracy"][f"delta_{run2.id}"] == -0.5


async def test_compare_runs_item_diffs(db_session: AsyncSession):
    run1, run2, _, _ = await _setup_two_runs(db_session)
    result = await comparison_service.compare_runs(db_session, [run1.id, run2.id])

    assert result["disagreement_count"] == 1
    disagreements = [d for d in result["item_diffs"] if d["disagree"]]
    assert len(disagreements) == 1


async def test_compare_three_runs(db_session: AsyncSession):
    run1, run2, _, _ = await _setup_two_runs(db_session)
    # Compare run1 with run2 and run1 again (just testing N>2 works)
    result = await comparison_service.compare_runs(db_session, [run1.id, run2.id, run1.id])
    assert len(result["run_ids"]) == 3


async def test_compare_runs_not_found(db_session: AsyncSession):
    with pytest.raises(ValueError, match="Run 9999 not found"):
        await comparison_service.compare_runs(db_session, [9999])


async def test_diff_target_configs(db_session: AsyncSession):
    _, _, t1, t2 = await _setup_two_runs(db_session)
    result = await comparison_service.diff_target_configs(db_session, [t1.id, t2.id])

    assert "inference_params" in result["differing_fields"]
    assert "model_name" in result["identical_fields"]
    assert "provider" in result["identical_fields"]
    # Temperature differs
    ip_diff = result["differing_fields"]["inference_params"]
    assert ip_diff[t1.id] == {"temperature": 0.0}
    assert ip_diff[t2.id] == {"temperature": 1.0}


async def test_diff_target_not_found(db_session: AsyncSession):
    with pytest.raises(ValueError, match="TargetConfiguration 9999 not found"):
        await comparison_service.diff_target_configs(db_session, [9999])
