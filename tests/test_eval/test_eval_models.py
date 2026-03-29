"""Tests for evaluation pipeline data models.

Verifies all 15 tables: creation, CRUD, FK constraints,
unique constraints, and JSON field round-trips.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_benchmark.eval.models.artifact import Artifact
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.machine import MachineProfile, MachineSnapshot
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunGroup, RunItemResult
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.models.base import create_session_factory


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    """Override db_session to use FK-enforcing engine for eval tests."""
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# ── Helpers ──


async def _make_dataset(session: AsyncSession, name: str = "test-ds") -> Dataset:
    ds = Dataset(name=name, description="A test dataset", source="manual")
    session.add(ds)
    await session.flush()
    return ds


async def _make_dataset_version(
    session: AsyncSession, dataset: Dataset, version: int = 1
) -> DatasetVersion:
    dv = DatasetVersion(dataset_id=dataset.id, version_number=version, item_count=0)
    session.add(dv)
    await session.flush()
    return dv


async def _make_test_case(session: AsyncSession, dv: DatasetVersion, index: int = 0) -> TestCase:
    tc = TestCase(
        dataset_version_id=dv.id,
        item_index=index,
        input_text="What is 2+2?",
        expected_output="4",
    )
    session.add(tc)
    await session.flush()
    return tc


async def _make_scorer(session: AsyncSession, name: str = "exact") -> Scorer:
    s = Scorer(name=name, scorer_type="exact_match")
    session.add(s)
    await session.flush()
    return s


async def _make_scorer_version(
    session: AsyncSession, scorer: Scorer, version: int = 1
) -> ScorerVersion:
    sv = ScorerVersion(
        scorer_id=scorer.id,
        version_number=version,
        config=json.dumps({"case_sensitive": True}),
    )
    session.add(sv)
    await session.flush()
    return sv


async def _make_eval_def(session: AsyncSession, name: str = "coding-eval") -> EvaluationDefinition:
    ed = EvaluationDefinition(name=name, execution_mode="sequential")
    session.add(ed)
    await session.flush()
    return ed


async def _make_machine(session: AsyncSession, hostname: str = "dgx-spark-01") -> MachineProfile:
    m = MachineProfile(hostname=hostname, hardware_class="dgx_spark")
    session.add(m)
    await session.flush()
    return m


async def _make_snapshot(session: AsyncSession, machine: MachineProfile) -> MachineSnapshot:
    snap = MachineSnapshot(
        machine_profile_id=machine.id,
        snapshot_data=json.dumps({"hostname": machine.hostname}),
    )
    session.add(snap)
    await session.flush()
    return snap


async def _make_target(
    session: AsyncSession,
    name: str = "gpt-4o-default",
    machine: MachineProfile | None = None,
) -> TargetConfiguration:
    t = TargetConfiguration(
        name=name,
        model_name="gpt-4o",
        provider="openai",
        inference_params=json.dumps({"temperature": 0.0}),
        machine_profile_id=machine.id if machine else None,
    )
    session.add(t)
    await session.flush()
    return t


async def _make_full_run_chain(session: AsyncSession):
    """Build the full FK chain needed to create a Run."""
    ds = await _make_dataset(session)
    dv = await _make_dataset_version(session, ds)
    tc = await _make_test_case(session, dv)
    scorer = await _make_scorer(session)
    sv = await _make_scorer_version(session, scorer)
    eval_def = await _make_eval_def(session)
    ev = EvaluationVersion(
        evaluation_id=eval_def.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps(
            [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5}]
        ),
    )
    session.add(ev)
    await session.flush()

    machine = await _make_machine(session)
    snap = await _make_snapshot(session, machine)
    target = await _make_target(session, machine=machine)

    return {
        "dataset": ds,
        "dataset_version": dv,
        "test_case": tc,
        "scorer": scorer,
        "scorer_version": sv,
        "eval_def": eval_def,
        "eval_version": ev,
        "machine": machine,
        "snapshot": snap,
        "target": target,
    }


# ── Dataset Tests ──


async def test_dataset_crud(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    assert ds.id is not None

    result = await db_session.execute(select(Dataset).where(Dataset.id == ds.id))
    loaded = result.scalar_one()
    assert loaded.name == "test-ds"
    assert loaded.source == "manual"


async def test_dataset_unique_name(db_session: AsyncSession):
    await _make_dataset(db_session, name="unique-ds")
    with pytest.raises(IntegrityError):
        await _make_dataset(db_session, name="unique-ds")


async def test_dataset_version_cascade(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds, version=1)
    assert dv.dataset_id == ds.id


async def test_dataset_version_unique_constraint(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    await _make_dataset_version(db_session, ds, version=1)
    with pytest.raises(IntegrityError):
        await _make_dataset_version(db_session, ds, version=1)


async def test_test_case_crud(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    tc = await _make_test_case(db_session, dv)
    assert tc.input_text == "What is 2+2?"
    assert tc.expected_output == "4"


async def test_test_case_metadata_json_roundtrip(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    metadata = {"task_family": "math", "difficulty": "easy", "tags": ["arithmetic"]}
    tc = TestCase(
        dataset_version_id=dv.id,
        item_index=0,
        input_text="1+1",
        metadata_json=json.dumps(metadata),
    )
    db_session.add(tc)
    await db_session.flush()

    result = await db_session.execute(select(TestCase).where(TestCase.id == tc.id))
    loaded = result.scalar_one()
    assert json.loads(loaded.metadata_json) == metadata


async def test_dataset_tags_json_roundtrip(db_session: AsyncSession):
    tags = ["coding", "math", "reasoning"]
    ds = Dataset(name="tagged-ds", tags=json.dumps(tags))
    db_session.add(ds)
    await db_session.flush()

    result = await db_session.execute(select(Dataset).where(Dataset.id == ds.id))
    loaded = result.scalar_one()
    assert json.loads(loaded.tags) == tags


# ── Scorer Tests ──


async def test_scorer_crud(db_session: AsyncSession):
    s = await _make_scorer(db_session)
    assert s.scorer_type == "exact_match"


async def test_scorer_version_config_roundtrip(db_session: AsyncSession):
    s = await _make_scorer(db_session)
    config = {"case_sensitive": False, "strip_whitespace": True, "normalize_unicode": True}
    sv = ScorerVersion(scorer_id=s.id, version_number=1, config=json.dumps(config))
    db_session.add(sv)
    await db_session.flush()

    result = await db_session.execute(select(ScorerVersion).where(ScorerVersion.id == sv.id))
    loaded = result.scalar_one()
    assert json.loads(loaded.config) == config


async def test_scorer_version_unique_constraint(db_session: AsyncSession):
    s = await _make_scorer(db_session)
    await _make_scorer_version(db_session, s, version=1)
    with pytest.raises(IntegrityError):
        await _make_scorer_version(db_session, s, version=1)


# ── Evaluation Tests ──


async def test_evaluation_definition_crud(db_session: AsyncSession):
    ed = await _make_eval_def(db_session)
    assert ed.execution_mode == "sequential"


async def test_evaluation_version_fk(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    scorer = await _make_scorer(db_session)
    sv = await _make_scorer_version(db_session, scorer)
    ed = await _make_eval_def(db_session)

    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    db_session.add(ev)
    await db_session.flush()
    assert ev.evaluation_id == ed.id
    assert ev.dataset_version_id == dv.id


async def test_evaluation_version_unique_constraint(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    ed = await _make_eval_def(db_session)

    ev1 = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config="[]",
    )
    db_session.add(ev1)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        ev2 = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dv.id,
            scorer_config="[]",
        )
        db_session.add(ev2)
        await db_session.flush()


async def test_evaluation_scorer_config_roundtrip(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    ed = await _make_eval_def(db_session)
    scorer_config = [
        {"scorer_version_id": 1, "weight": 0.7, "pass_threshold": 0.8},
        {"scorer_version_id": 2, "weight": 0.3, "pass_threshold": 0.5},
    ]
    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps(scorer_config),
        preprocessing=json.dumps({"strip": True}),
        pass_criteria=json.dumps({"min_pass_rate": 0.9}),
    )
    db_session.add(ev)
    await db_session.flush()

    result = await db_session.execute(
        select(EvaluationVersion).where(EvaluationVersion.id == ev.id)
    )
    loaded = result.scalar_one()
    assert json.loads(loaded.scorer_config) == scorer_config
    assert json.loads(loaded.preprocessing) == {"strip": True}
    assert json.loads(loaded.pass_criteria) == {"min_pass_rate": 0.9}


# ── Machine Tests ──


async def test_machine_profile_crud(db_session: AsyncSession):
    m = await _make_machine(db_session)
    assert m.hardware_class == "dgx_spark"


async def test_machine_hostname_unique(db_session: AsyncSession):
    await _make_machine(db_session, hostname="host-1")
    with pytest.raises(IntegrityError):
        await _make_machine(db_session, hostname="host-1")


async def test_machine_snapshot_data_roundtrip(db_session: AsyncSession):
    m = await _make_machine(db_session)
    data = {
        "hostname": "dgx-spark-01",
        "gpu_description": "NVIDIA Grace Blackwell",
        "runtime_version": "ollama 0.5.3",
    }
    snap = MachineSnapshot(machine_profile_id=m.id, snapshot_data=json.dumps(data))
    db_session.add(snap)
    await db_session.flush()

    result = await db_session.execute(select(MachineSnapshot).where(MachineSnapshot.id == snap.id))
    loaded = result.scalar_one()
    assert json.loads(loaded.snapshot_data) == data


async def test_machine_accelerator_details_json(db_session: AsyncSession):
    accel = {"vram_gb": 12, "cuda_cores": 5888, "tensor_cores": 184}
    m = MachineProfile(
        hostname="rtx-workstation",
        hardware_class="rtx_4070_workstation",
        accelerator_details=json.dumps(accel),
        runtime_availability=json.dumps(["ollama", "vllm"]),
    )
    db_session.add(m)
    await db_session.flush()

    result = await db_session.execute(select(MachineProfile).where(MachineProfile.id == m.id))
    loaded = result.scalar_one()
    assert json.loads(loaded.accelerator_details) == accel
    assert json.loads(loaded.runtime_availability) == ["ollama", "vllm"]


# ── Target Tests ──


async def test_target_configuration_crud(db_session: AsyncSession):
    t = await _make_target(db_session)
    assert t.model_name == "gpt-4o"
    assert t.provider == "openai"


async def test_target_name_unique(db_session: AsyncSession):
    await _make_target(db_session, name="target-a")
    with pytest.raises(IntegrityError):
        await _make_target(db_session, name="target-a")


async def test_target_inference_params_roundtrip(db_session: AsyncSession):
    params = {"temperature": 0.7, "top_p": 0.9, "max_tokens": 4096, "stop": ["\n"]}
    t = TargetConfiguration(
        name="custom-target",
        model_name="claude-3.5-sonnet",
        provider="anthropic",
        inference_params=json.dumps(params),
        runtime_options=json.dumps({"timeout": 60}),
    )
    db_session.add(t)
    await db_session.flush()

    result = await db_session.execute(
        select(TargetConfiguration).where(TargetConfiguration.id == t.id)
    )
    loaded = result.scalar_one()
    assert json.loads(loaded.inference_params) == params
    assert json.loads(loaded.runtime_options) == {"timeout": 60}


async def test_target_machine_fk(db_session: AsyncSession):
    m = await _make_machine(db_session)
    t = await _make_target(db_session, name="linked-target", machine=m)
    assert t.machine_profile_id == m.id


# ── Run Tests ──


async def test_run_group_crud(db_session: AsyncSession):
    rg = RunGroup(name="matrix-1", execution_type="matrix")
    db_session.add(rg)
    await db_session.flush()
    assert rg.id is not None


async def test_run_full_lifecycle(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    run = Run(
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        machine_snapshot_id=chain["snapshot"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="queued",
        trigger_type="manual",
        total_items=1,
    )
    db_session.add(run)
    await db_session.flush()

    assert run.status == "queued"
    assert run.evaluation_version_id == chain["eval_version"].id
    assert run.target_config_id == chain["target"].id
    assert run.machine_snapshot_id == chain["snapshot"].id


async def test_run_with_group(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    rg = RunGroup(name="batch-test", execution_type="batch")
    db_session.add(rg)
    await db_session.flush()

    run = Run(
        run_group_id=rg.id,
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="queued",
    )
    db_session.add(run)
    await db_session.flush()
    assert run.run_group_id == rg.id


async def test_run_item_result_crud(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    run = Run(
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="running",
        total_items=1,
    )
    db_session.add(run)
    await db_session.flush()

    scorer_results = [{"scorer_version_id": chain["scorer_version"].id, "score": 1.0, "pass": True}]
    item = RunItemResult(
        run_id=run.id,
        test_case_id=chain["test_case"].id,
        item_index=0,
        input_sent="What is 2+2?",
        raw_output="4",
        scorer_results=json.dumps(scorer_results),
        overall_pass=True,
        latency_ms=150.5,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost_estimate_usd=0.0001,
    )
    db_session.add(item)
    await db_session.flush()

    result = await db_session.execute(select(RunItemResult).where(RunItemResult.id == item.id))
    loaded = result.scalar_one()
    assert loaded.overall_pass is True
    assert loaded.latency_ms == 150.5
    assert json.loads(loaded.scorer_results) == scorer_results


async def test_run_aggregate_metric_crud(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    run = Run(
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="completed",
    )
    db_session.add(run)
    await db_session.flush()

    metric = RunAggregateMetric(
        run_id=run.id,
        metric_name="overall_accuracy",
        metric_value=0.95,
        metric_metadata=json.dumps({"count": 100, "std_dev": 0.02}),
    )
    db_session.add(metric)
    await db_session.flush()

    result = await db_session.execute(
        select(RunAggregateMetric).where(RunAggregateMetric.id == metric.id)
    )
    loaded = result.scalar_one()
    assert loaded.metric_value == 0.95
    assert json.loads(loaded.metric_metadata) == {"count": 100, "std_dev": 0.02}


async def test_run_aggregate_metric_unique(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    run = Run(
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="completed",
    )
    db_session.add(run)
    await db_session.flush()

    m1 = RunAggregateMetric(run_id=run.id, metric_name="accuracy", metric_value=0.9)
    db_session.add(m1)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        m2 = RunAggregateMetric(run_id=run.id, metric_name="accuracy", metric_value=0.8)
        db_session.add(m2)
        await db_session.flush()


# ── Artifact Tests ──


async def test_artifact_crud(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    run = Run(
        evaluation_version_id=chain["eval_version"].id,
        target_config_id=chain["target"].id,
        dataset_version_id=chain["dataset_version"].id,
        status="completed",
    )
    db_session.add(run)
    await db_session.flush()

    art = Artifact(
        run_id=run.id,
        artifact_type="result_table",
        filename="results.json",
        file_path="./artifacts/run_1/results.json",
        size_bytes=1024,
        mime_type="application/json",
    )
    db_session.add(art)
    await db_session.flush()

    result = await db_session.execute(select(Artifact).where(Artifact.id == art.id))
    loaded = result.scalar_one()
    assert loaded.artifact_type == "result_table"
    assert loaded.size_bytes == 1024


# ── FK Constraint Tests ──


async def test_dataset_version_fk_requires_dataset(db_session: AsyncSession):
    with pytest.raises(IntegrityError):
        dv = DatasetVersion(dataset_id=9999, version_number=1, item_count=0)
        db_session.add(dv)
        await db_session.flush()


async def test_test_case_fk_requires_version(db_session: AsyncSession):
    with pytest.raises(IntegrityError):
        tc = TestCase(dataset_version_id=9999, item_index=0, input_text="test")
        db_session.add(tc)
        await db_session.flush()


async def test_scorer_version_fk_requires_scorer(db_session: AsyncSession):
    with pytest.raises(IntegrityError):
        sv = ScorerVersion(scorer_id=9999, version_number=1, config="{}")
        db_session.add(sv)
        await db_session.flush()


async def test_evaluation_version_fk_requires_eval_def(db_session: AsyncSession):
    ds = await _make_dataset(db_session)
    dv = await _make_dataset_version(db_session, ds)
    with pytest.raises(IntegrityError):
        ev = EvaluationVersion(
            evaluation_id=9999,
            version_number=1,
            dataset_version_id=dv.id,
            scorer_config="[]",
        )
        db_session.add(ev)
        await db_session.flush()


async def test_run_fk_requires_eval_version(db_session: AsyncSession):
    chain = await _make_full_run_chain(db_session)
    with pytest.raises(IntegrityError):
        run = Run(
            evaluation_version_id=9999,
            target_config_id=chain["target"].id,
            dataset_version_id=chain["dataset_version"].id,
            status="queued",
        )
        db_session.add(run)
        await db_session.flush()


async def test_artifact_fk_requires_run(db_session: AsyncSession):
    with pytest.raises(IntegrityError):
        art = Artifact(
            run_id=9999,
            artifact_type="log",
            filename="log.txt",
            file_path="/tmp/log.txt",
        )
        db_session.add(art)
        await db_session.flush()
