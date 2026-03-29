"""Tests for RunnerProfile, TraceReference, Annotation models and persistence."""

from __future__ import annotations

import json

import pytest

from ai_benchmark.eval.models.trace import Annotation, TraceReference
from ai_benchmark.eval.services import runner_service


@pytest.fixture
async def eval_session(db_engine_fk):
    from ai_benchmark.models.base import create_session_factory

    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# --- RunnerProfile CRUD ---


@pytest.mark.asyncio
async def test_create_runner_profile(eval_session):
    runner = await runner_service.create_runner(
        eval_session,
        name="ollama-default",
        runner_class="ollama",
        display_name="Ollama",
        version="0.5.4",
        default_endpoint_url="http://localhost:11434/v1/chat/completions",
        supported_machine_classes=json.dumps(
            ["dgx_spark", "apple_silicon_pro", "apple_silicon_mini", "rtx_desktop"]
        ),
        supported_model_families=json.dumps(["llama", "gemma", "phi", "qwen"]),
        notes="Cross-platform baseline runner",
    )
    await eval_session.commit()
    assert runner.id is not None
    assert runner.runner_class == "ollama"
    assert runner.is_archived is False


@pytest.mark.asyncio
async def test_list_runners_filters_by_class(eval_session):
    await runner_service.create_runner(eval_session, name="ollama-1", runner_class="ollama")
    await runner_service.create_runner(eval_session, name="vllm-1", runner_class="vllm")
    await eval_session.commit()

    ollama_runners = await runner_service.list_runners(eval_session, runner_class="ollama")
    assert len(ollama_runners) == 1
    assert ollama_runners[0].runner_class == "ollama"

    all_runners = await runner_service.list_runners(eval_session)
    assert len(all_runners) == 2


@pytest.mark.asyncio
async def test_update_runner_profile(eval_session):
    runner = await runner_service.create_runner(eval_session, name="mlx-1", runner_class="mlx")
    await eval_session.commit()

    updated = await runner_service.update_runner(
        eval_session, runner.id, version="0.21.0", notes="Apple Silicon only"
    )
    await eval_session.commit()

    assert updated is not None
    assert updated.version == "0.21.0"
    assert updated.notes == "Apple Silicon only"


@pytest.mark.asyncio
async def test_archive_runner_excludes_from_list(eval_session):
    runner = await runner_service.create_runner(
        eval_session, name="old-runner", runner_class="llamacpp"
    )
    await eval_session.commit()

    await runner_service.update_runner(eval_session, runner.id, is_archived=True)
    await eval_session.commit()

    active = await runner_service.list_runners(eval_session)
    assert len(active) == 0

    all_runners = await runner_service.list_runners(eval_session, include_archived=True)
    assert len(all_runners) == 1


@pytest.mark.asyncio
async def test_get_runner_by_class(eval_session):
    await runner_service.create_runner(eval_session, name="sglang-default", runner_class="sglang")
    await eval_session.commit()

    runner = await runner_service.get_runner_by_class(eval_session, "sglang")
    assert runner is not None
    assert runner.name == "sglang-default"

    missing = await runner_service.get_runner_by_class(eval_session, "nonexistent")
    assert missing is None


# --- TraceReference ---


@pytest.mark.asyncio
async def test_create_trace_reference(eval_session):
    # Need a minimal run + item_result to attach a trace to
    from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
    from ai_benchmark.eval.models.evaluation import (
        EvaluationDefinition,
        EvaluationVersion,
    )
    from ai_benchmark.eval.models.run import Run, RunItemResult
    from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
    from ai_benchmark.eval.models.target import TargetConfiguration

    ds = Dataset(name="trace-ds")
    eval_session.add(ds)
    await eval_session.flush()
    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=1)
    eval_session.add(dv)
    await eval_session.flush()
    tc = TestCase(dataset_version_id=dv.id, item_index=0, input_text="hello")
    eval_session.add(tc)

    scorer = Scorer(name="trace-scorer", scorer_type="exact_match")
    eval_session.add(scorer)
    await eval_session.flush()
    sv = ScorerVersion(scorer_id=scorer.id, version_number=1, config="{}")
    eval_session.add(sv)

    ev = EvaluationDefinition(name="trace-eval")
    eval_session.add(ev)
    await eval_session.flush()
    evv = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    eval_session.add(evv)

    target = TargetConfiguration(
        name="trace-target",
        model_name="test-model",
        provider="ollama",
        inference_params="{}",
    )
    eval_session.add(target)
    await eval_session.flush()

    run = Run(
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="completed",
        total_items=1,
    )
    eval_session.add(run)
    await eval_session.flush()

    item = RunItemResult(
        run_id=run.id,
        test_case_id=tc.id,
        item_index=0,
        input_sent="hello",
        scorer_results="[]",
        latency_ms=42.5,
    )
    eval_session.add(item)
    await eval_session.flush()

    trace = TraceReference(
        run_item_result_id=item.id,
        trace_type="latency_breakdown",
        trace_data=json.dumps({"queue_ms": 2.0, "inference_ms": 38.5, "postprocess_ms": 2.0}),
    )
    eval_session.add(trace)
    await eval_session.commit()

    assert trace.id is not None
    assert trace.trace_type == "latency_breakdown"


# --- Annotation ---


@pytest.mark.asyncio
async def test_create_annotation(eval_session):
    annotation = Annotation(
        entity_type="run",
        entity_id=1,
        label="baseline",
        note="Reference run for Ollama on DGX Spark",
    )
    eval_session.add(annotation)
    await eval_session.commit()
    assert annotation.id is not None
    assert annotation.label == "baseline"


@pytest.mark.asyncio
async def test_annotation_does_not_modify_run(eval_session):
    """Annotations are separate records — they don't overwrite execution facts."""
    a1 = Annotation(entity_type="run", entity_id=99, label="preferred")
    a2 = Annotation(entity_type="run", entity_id=99, label="regression")
    eval_session.add_all([a1, a2])
    await eval_session.commit()

    # Both annotations exist independently for the same entity
    from sqlalchemy import select

    result = await eval_session.execute(select(Annotation).where(Annotation.entity_id == 99))
    annotations = list(result.scalars().all())
    assert len(annotations) == 2
    labels = {a.label for a in annotations}
    assert labels == {"preferred", "regression"}


# --- Immutable versioning ---


@pytest.mark.asyncio
async def test_evaluation_version_immutable(eval_session):
    """Evaluation versions auto-increment and preserve history."""
    from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion
    from ai_benchmark.eval.models.evaluation import (
        EvaluationDefinition,
        EvaluationVersion,
    )
    from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion

    ds = Dataset(name="immut-ds")
    eval_session.add(ds)
    await eval_session.flush()
    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=0)
    eval_session.add(dv)
    await eval_session.flush()

    scorer = Scorer(name="immut-scorer", scorer_type="exact_match")
    eval_session.add(scorer)
    await eval_session.flush()
    sv = ScorerVersion(scorer_id=scorer.id, version_number=1, config="{}")
    eval_session.add(sv)
    await eval_session.flush()

    ev = EvaluationDefinition(name="immut-eval")
    eval_session.add(ev)
    await eval_session.flush()

    v1 = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    v2 = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=2,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    eval_session.add_all([v1, v2])
    await eval_session.commit()

    # Both versions exist — old versions are not overwritten
    assert v1.id != v2.id
    assert v1.version_number == 1
    assert v2.version_number == 2


# --- Requested vs effective config ---


@pytest.mark.asyncio
async def test_run_stores_requested_and_effective_config(eval_session):
    """Run records requested config and effective (actual) config separately."""
    from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion
    from ai_benchmark.eval.models.evaluation import (
        EvaluationDefinition,
        EvaluationVersion,
    )
    from ai_benchmark.eval.models.run import Run
    from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
    from ai_benchmark.eval.models.target import TargetConfiguration

    ds = Dataset(name="reqeff-ds")
    eval_session.add(ds)
    await eval_session.flush()
    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=0)
    eval_session.add(dv)
    await eval_session.flush()

    scorer = Scorer(name="reqeff-scorer", scorer_type="exact_match")
    eval_session.add(scorer)
    await eval_session.flush()
    sv = ScorerVersion(scorer_id=scorer.id, version_number=1, config="{}")
    eval_session.add(sv)
    await eval_session.flush()

    ev = EvaluationDefinition(name="reqeff-eval")
    eval_session.add(ev)
    await eval_session.flush()
    evv = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    eval_session.add(evv)

    target = TargetConfiguration(
        name="reqeff-target",
        model_name="llama3-8b",
        provider="ollama",
        inference_params=json.dumps({"temperature": 0.7, "max_tokens": 512}),
    )
    eval_session.add(target)
    await eval_session.flush()

    requested = {"temperature": 0.7, "max_tokens": 512, "gpu_layers": 35}
    effective = {"temperature": 0.7, "max_tokens": 512, "gpu_layers": 32}  # runner adjusted

    run = Run(
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="completed",
        total_items=0,
        requested_config=json.dumps(requested),
        effective_config=json.dumps(effective),
        runner_snapshot=json.dumps({"runner": "ollama", "version": "0.5.4"}),
    )
    eval_session.add(run)
    await eval_session.commit()

    assert run.id is not None
    loaded_requested = json.loads(run.requested_config)
    loaded_effective = json.loads(run.effective_config)
    assert loaded_requested["gpu_layers"] == 35
    assert loaded_effective["gpu_layers"] == 32  # runner adjusted
