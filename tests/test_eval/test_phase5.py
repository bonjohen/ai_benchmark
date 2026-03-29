"""Tests for Phase 5: Target configurations, compatibility validation, and matrix expansion."""

from __future__ import annotations

import json

import pytest

from ai_benchmark.eval.services import (
    dataset_service,
    eval_service,
    machine_service,
    runner_service,
    scorer_service,
    target_service,
)
from ai_benchmark.eval.services.matrix import expand_matrix
from ai_benchmark.eval.services.validation import validate_target_compatibility


@pytest.fixture
async def session(db_engine_fk):
    from ai_benchmark.models.base import create_session_factory

    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


async def _create_eval_chain(session):
    """Create a minimal eval chain for run creation."""
    ds = await dataset_service.create_dataset(session, name="p5-ds")
    dv = await dataset_service.create_version(
        session,
        dataset_id=ds.id,
        items=[{"input_text": "test"}],
    )
    scorer = await scorer_service.create_scorer(
        session, name="p5-scorer", scorer_type="exact_match"
    )
    sv = await scorer_service.create_version(session, scorer_id=scorer.id, config={})
    ev = await eval_service.create_evaluation(session, name="p5-eval")
    evv = await eval_service.create_version(
        session,
        evaluation_id=ev.id,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
    )
    return ds, dv, scorer, sv, ev, evv


# --- Target cloning ---


@pytest.mark.asyncio
async def test_clone_target_preserves_fields(session):
    machine = await machine_service.create_profile(
        session, hostname="clone-host", hardware_class="rtx_desktop"
    )
    original = await target_service.create_target(
        session,
        name="original",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={"temperature": 0.7, "max_tokens": 512},
        machine_profile_id=machine.id,
        tags=["baseline"],
        notes="Original config",
    )
    await session.commit()

    clone = await target_service.clone_target(session, original.id, new_name="clone-1")
    await session.commit()

    assert clone.id != original.id
    assert clone.name == "clone-1"
    assert clone.model_name == "llama3-8b"
    assert clone.provider == "ollama"
    assert clone.machine_profile_id == machine.id
    assert json.loads(clone.inference_params) == {"temperature": 0.7, "max_tokens": 512}


@pytest.mark.asyncio
async def test_clone_target_with_overrides(session):
    original = await target_service.create_target(
        session,
        name="base-cfg",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={"temperature": 0.7},
    )
    await session.commit()

    clone = await target_service.clone_target(
        session,
        original.id,
        new_name="warm-cfg",
        overrides={"inference_params": {"temperature": 1.0}},
    )
    await session.commit()

    assert json.loads(clone.inference_params) == {"temperature": 1.0}
    assert clone.model_name == "llama3-8b"  # unchanged


@pytest.mark.asyncio
async def test_clone_target_not_found(session):
    with pytest.raises(ValueError, match="not found"):
        await target_service.clone_target(session, 99999, new_name="ghost")


# --- Target tagging ---


@pytest.mark.asyncio
async def test_target_tagging(session):
    target = await target_service.create_target(
        session,
        name="tagged",
        model_name="phi-3",
        provider="ollama",
        inference_params={},
        tags=["baseline", "standard-laptop"],
    )
    await session.commit()

    tags = json.loads(target.tags)
    assert "baseline" in tags
    assert "standard-laptop" in tags


# --- Target compatibility validation ---


@pytest.mark.asyncio
async def test_validate_compatible_target(session):
    runner = await runner_service.create_runner(
        session,
        name="compat-ollama",
        runner_class="ollama",
        supported_machine_classes=json.dumps(["rtx_desktop"]),
    )
    machine = await machine_service.create_profile(
        session, hostname="compat-rtx", hardware_class="rtx_desktop"
    )
    target = await target_service.create_target(
        session,
        name="compat-target",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={},
        machine_profile_id=machine.id,
    )
    # Set runner_profile_id directly (not in create_target API)
    target.runner_profile_id = runner.id
    await session.flush()
    await session.commit()

    result = await validate_target_compatibility(session, target.id)
    assert result.valid
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_validate_incompatible_target(session):
    runner = await runner_service.create_runner(
        session,
        name="incompat-mlx",
        runner_class="mlx",
        supported_machine_classes=json.dumps(["apple_silicon_pro", "apple_silicon_mini"]),
    )
    machine = await machine_service.create_profile(
        session, hostname="incompat-rtx", hardware_class="rtx_desktop"
    )
    target = await target_service.create_target(
        session,
        name="incompat-target",
        model_name="llama3-8b",
        provider="mlx",
        inference_params={},
        machine_profile_id=machine.id,
    )
    target.runner_profile_id = runner.id
    await session.flush()
    await session.commit()

    result = await validate_target_compatibility(session, target.id)
    assert not result.valid
    assert any("not compatible" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_target_provider_mismatch_warning(session):
    runner = await runner_service.create_runner(
        session,
        name="mismatch-ollama",
        runner_class="ollama",
    )
    target = await target_service.create_target(
        session,
        name="mismatch-target",
        model_name="llama3-8b",
        provider="vllm",  # doesn't match runner_class
        inference_params={},
    )
    target.runner_profile_id = runner.id
    await session.flush()
    await session.commit()

    result = await validate_target_compatibility(session, target.id)
    assert result.valid  # warning, not error
    assert len(result.warnings) == 1
    assert "differs from" in result.warnings[0]


# --- Matrix expansion ---


@pytest.mark.asyncio
async def test_matrix_expansion_basic(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    t1 = await target_service.create_target(
        session,
        name="m-t1",
        model_name="m1",
        provider="ollama",
        inference_params={},
    )
    t2 = await target_service.create_target(
        session,
        name="m-t2",
        model_name="m2",
        provider="ollama",
        inference_params={},
    )
    await session.commit()

    result = await expand_matrix(
        session,
        evaluation_version_id=evv.id,
        target_config_ids=[t1.id, t2.id],
        dataset_version_id=dv.id,
        name="test-matrix",
        validate=False,  # skip validation for speed
    )
    await session.commit()

    assert result.run_group is not None
    assert result.run_group.execution_type == "matrix"
    assert len(result.runs) == 2
    assert len(result.skipped) == 0
    assert all(r.trigger_type == "matrix" for r in result.runs)


@pytest.mark.asyncio
async def test_matrix_expansion_with_tags(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    t1 = await target_service.create_target(
        session,
        name="mt-t1",
        model_name="m1",
        provider="ollama",
        inference_params={},
    )
    await session.commit()

    result = await expand_matrix(
        session,
        evaluation_version_id=evv.id,
        target_config_ids=[t1.id],
        dataset_version_id=dv.id,
        tags=["nightly", "smoke"],
        validate=False,
    )
    await session.commit()

    assert result.run_group is not None
    assert json.loads(result.run_group.tags) == ["nightly", "smoke"]


@pytest.mark.asyncio
async def test_matrix_expansion_skips_incompatible(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    runner = await runner_service.create_runner(
        session,
        name="mx-mlx",
        runner_class="mlx",
        supported_machine_classes=json.dumps(["apple_silicon_pro"]),
    )
    machine = await machine_service.create_profile(
        session, hostname="mx-rtx", hardware_class="rtx_desktop"
    )

    target = await target_service.create_target(
        session,
        name="mx-incompat",
        model_name="llama3-8b",
        provider="mlx",
        inference_params={},
        machine_profile_id=machine.id,
    )
    target.runner_profile_id = runner.id
    await session.flush()
    await session.commit()

    result = await expand_matrix(
        session,
        evaluation_version_id=evv.id,
        target_config_ids=[target.id],
        dataset_version_id=dv.id,
        skip_incompatible=True,
    )
    await session.commit()

    assert len(result.runs) == 0
    assert len(result.skipped) == 1
    assert result.skipped[0]["target_config_id"] == target.id


@pytest.mark.asyncio
async def test_matrix_expansion_captures_machine_snapshot(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    machine = await machine_service.create_profile(
        session,
        hostname="mx-snap-host",
        hardware_class="rtx_desktop",
        ram_gb=32,
    )
    target = await target_service.create_target(
        session,
        name="mx-snap",
        model_name="m1",
        provider="ollama",
        inference_params={},
        machine_profile_id=machine.id,
    )
    await session.commit()

    result = await expand_matrix(
        session,
        evaluation_version_id=evv.id,
        target_config_ids=[target.id],
        dataset_version_id=dv.id,
        validate=False,
    )
    await session.commit()

    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.machine_snapshot_id is not None
    assert run.requested_machine_profile_id == machine.id


@pytest.mark.asyncio
async def test_matrix_expansion_empty_targets(session):
    ds, dv, *_ = await _create_eval_chain(session)

    result = await expand_matrix(
        session,
        evaluation_version_id=1,
        target_config_ids=[],
        dataset_version_id=dv.id,
    )
    assert len(result.errors) == 1
    assert "No target" in result.errors[0]


# --- Requested vs effective config on run ---


@pytest.mark.asyncio
async def test_run_requested_effective_config(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="reqeff-target",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={"temperature": 0.7, "gpu_layers": 35},
    )
    await session.commit()

    from ai_benchmark.eval.models.run import Run

    run = Run(
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="completed",
        total_items=0,
        requested_config=json.dumps({"temperature": 0.7, "gpu_layers": 35}),
        effective_config=json.dumps({"temperature": 0.7, "gpu_layers": 32}),
    )
    session.add(run)
    await session.commit()

    requested = json.loads(run.requested_config)
    effective = json.loads(run.effective_config)
    assert requested["gpu_layers"] == 35
    assert effective["gpu_layers"] == 32
