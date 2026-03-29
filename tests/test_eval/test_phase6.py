"""Tests for Phase 6: Execution engine, dispatch, constraints, progress, and resume."""

from __future__ import annotations

import pytest

from ai_benchmark.eval.execution.dispatch import (
    ACTIVE_STATES,
    RUN_STATES,
    TERMINAL_STATES,
    RunConstraints,
    evaluate_dispatch,
    get_group_progress,
    get_queue,
    get_run_progress,
    resume_run,
)
from ai_benchmark.eval.services import (
    dataset_service,
    eval_service,
    machine_service,
    run_service,
    scorer_service,
    target_service,
)


@pytest.fixture
async def session(db_engine_fk):
    from ai_benchmark.models.base import create_session_factory

    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


async def _create_eval_chain(session):
    """Create a minimal eval chain."""
    ds = await dataset_service.create_dataset(session, name="p6-ds")
    dv = await dataset_service.create_version(
        session,
        dataset_id=ds.id,
        items=[{"input_text": "test"}],
    )
    scorer = await scorer_service.create_scorer(
        session, name="p6-scorer", scorer_type="exact_match"
    )
    sv = await scorer_service.create_version(session, scorer_id=scorer.id, config={})
    ev = await eval_service.create_evaluation(session, name="p6-eval")
    evv = await eval_service.create_version(
        session,
        evaluation_id=ev.id,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
    )
    return ds, dv, scorer, sv, ev, evv


# --- Run state constants ---


class TestRunStates:
    def test_all_states_defined(self):
        assert len(RUN_STATES) == 11

    def test_terminal_states(self):
        for s in TERMINAL_STATES:
            assert s in RUN_STATES

    def test_active_states(self):
        for s in ACTIVE_STATES:
            assert s in RUN_STATES

    def test_queued_is_neither_terminal_nor_active(self):
        assert "queued" not in TERMINAL_STATES
        assert "queued" not in ACTIVE_STATES


# --- Dispatch evaluation ---


@pytest.mark.asyncio
async def test_dispatch_allowed(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="disp-target",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await session.commit()

    decision = await evaluate_dispatch(session, run)
    assert decision.allowed


@pytest.mark.asyncio
async def test_dispatch_runner_allow_list(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="disp-vllm",
        model_name="llama3-8b",
        provider="vllm",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await session.commit()

    constraints = RunConstraints(runner_allow_list=["ollama", "mlx"])
    decision = await evaluate_dispatch(session, run, constraints)
    assert not decision.allowed
    assert "runner allow-list" in decision.reason


@pytest.mark.asyncio
async def test_dispatch_machine_allow_list(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    machine = await machine_service.create_profile(
        session, hostname="disp-rtx", hardware_class="rtx_desktop"
    )
    target = await target_service.create_target(
        session,
        name="disp-mach",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={},
        machine_profile_id=machine.id,
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await session.commit()

    constraints = RunConstraints(machine_allow_list=["dgx_spark"])
    decision = await evaluate_dispatch(session, run, constraints)
    assert not decision.allowed
    assert "allow-list" in decision.reason


@pytest.mark.asyncio
async def test_dispatch_concurrent_limit(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="disp-conc",
        model_name="llama3-8b",
        provider="ollama",
        inference_params={},
    )

    # Create runs in active states to fill the limit
    for _i in range(3):
        r = await run_service.create_run(
            session,
            evaluation_version_id=evv.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
        )
        r.status = "running_generation"
    await session.flush()

    new_run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await session.commit()

    constraints = RunConstraints(max_concurrent_runs=3)
    decision = await evaluate_dispatch(session, new_run, constraints)
    assert not decision.allowed
    assert "Concurrent run limit" in decision.reason


# --- Queue priority ---


@pytest.mark.asyncio
async def test_queue_priority_ordering(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="q-target",
        model_name="m",
        provider="ollama",
        inference_params={},
    )
    low = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        priority=1,
    )
    high = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        priority=10,
    )
    await session.commit()

    queue = await get_queue(session)
    assert len(queue) >= 2
    assert queue[0].id == high.id  # highest priority first
    assert queue[1].id == low.id


# --- Resume ---


@pytest.mark.asyncio
async def test_resume_failed_run(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="resume-target",
        model_name="m",
        provider="ollama",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await run_service.update_status(session, run.id, "failed", error_message="timeout")
    await session.commit()

    resumed = await resume_run(session, run.id)
    assert resumed.status == "queued"
    assert resumed.error_message is None


@pytest.mark.asyncio
async def test_resume_completed_run_rejected(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="no-resume",
        model_name="m",
        provider="ollama",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    await run_service.update_status(session, run.id, "completed")
    await session.commit()

    with pytest.raises(ValueError, match="Cannot resume"):
        await resume_run(session, run.id)


# --- Progress tracking ---


@pytest.mark.asyncio
async def test_run_progress(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="prog-target",
        model_name="m",
        provider="ollama",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        total_items=10,
    )
    run.completed_items = 7
    run.failed_items = 1
    run.status = "running_generation"
    await session.flush()
    await session.commit()

    progress = await get_run_progress(session, run.id)
    assert progress["total_items"] == 10
    assert progress["completed_items"] == 7
    assert progress["failed_items"] == 1
    assert progress["processed_items"] == 8
    assert progress["progress_pct"] == 80.0


@pytest.mark.asyncio
async def test_group_progress(session):
    from ai_benchmark.eval.models.run import RunGroup

    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="gp-target",
        model_name="m",
        provider="ollama",
        inference_params={},
    )

    rg = RunGroup(name="gp-group", execution_type="matrix")
    session.add(rg)
    await session.flush()

    r1 = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        total_items=5,
        run_group_id=rg.id,
    )
    r2 = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        total_items=5,
        run_group_id=rg.id,
    )
    r1.completed_items = 5
    r1.status = "completed"
    r2.completed_items = 2
    r2.failed_items = 1
    r2.status = "running_generation"
    await session.flush()
    await session.commit()

    progress = await get_group_progress(session, rg.id)
    assert progress["total_runs"] == 2
    assert progress["total_items"] == 10
    assert progress["completed_items"] == 7
    assert progress["failed_items"] == 1
    assert progress["status_counts"]["completed"] == 1
    assert progress["status_counts"]["running_generation"] == 1


# --- Status transitions ---


@pytest.mark.asyncio
async def test_status_transitions(session):
    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = await target_service.create_target(
        session,
        name="trans-target",
        model_name="m",
        provider="ollama",
        inference_params={},
    )
    run = await run_service.create_run(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
    )
    assert run.status == "queued"

    # Progress through expanded states
    await run_service.update_status(session, run.id, "validating")
    await session.refresh(run)
    assert run.status == "validating"

    await run_service.update_status(session, run.id, "preparing")
    await session.refresh(run)
    assert run.status == "preparing"

    await run_service.update_status(session, run.id, "running_generation")
    await session.refresh(run)
    assert run.status == "running_generation"
    assert run.started_at is not None

    await run_service.update_status(session, run.id, "running_scorers")
    await session.refresh(run)
    assert run.status == "running_scorers"
    assert run.scoring_started_at is not None

    await run_service.update_status(session, run.id, "aggregating")
    await session.refresh(run)
    assert run.status == "aggregating"

    await run_service.update_status(session, run.id, "completed")
    await session.refresh(run)
    assert run.status == "completed"
    assert run.completed_at is not None
