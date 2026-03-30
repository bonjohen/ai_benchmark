"""Tests for Phase 3: Runner and Machine Registry — compatibility, seeding, snapshots."""

from __future__ import annotations

import json

import pytest

from ai_benchmark.eval.services import machine_service, runner_service
from ai_benchmark.eval.services.compatibility import (
    DEFAULT_COMPATIBILITY,
    get_compatible_machines,
    get_compatible_runners,
    is_compatible,
    is_runner_compatible_with_machine,
)
from ai_benchmark.eval.services.seed import (
    MACHINE_SEEDS,
    RUNNER_SEEDS,
    seed_all,
    seed_machines,
    seed_runners,
)


@pytest.fixture
async def session(db_engine_fk):
    from ai_benchmark.models.base import create_session_factory

    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# --- Static compatibility ---


class TestStaticCompatibility:
    def test_ollama_cross_platform(self):
        assert is_compatible("ollama", "dgx_spark")
        assert is_compatible("ollama", "apple_silicon_pro")
        assert is_compatible("ollama", "rtx_desktop")
        assert not is_compatible("ollama", "edge_device")

    def test_mlx_apple_only(self):
        assert is_compatible("mlx", "apple_silicon_pro")
        assert is_compatible("mlx", "apple_silicon_mini")
        assert not is_compatible("mlx", "dgx_spark")
        assert not is_compatible("mlx", "rtx_desktop")

    def test_vllm_nvidia_only(self):
        assert is_compatible("vllm", "dgx_spark")
        assert is_compatible("vllm", "rtx_desktop")
        assert not is_compatible("vllm", "apple_silicon_pro")
        assert not is_compatible("vllm", "intel_ai_laptop")

    def test_openvino_intel_only(self):
        assert is_compatible("openvino", "intel_ai_laptop")
        assert not is_compatible("openvino", "dgx_spark")
        assert not is_compatible("openvino", "apple_silicon_pro")

    def test_llamacpp_runs_everywhere(self):
        assert is_compatible("llamacpp", "dgx_spark")
        assert is_compatible("llamacpp", "apple_silicon_pro")
        assert is_compatible("llamacpp", "rtx_desktop")
        assert is_compatible("llamacpp", "edge_device")

    def test_tensorrt_nvidia_only(self):
        assert is_compatible("tensorrt", "dgx_spark")
        assert is_compatible("tensorrt", "rtx_desktop")
        assert not is_compatible("tensorrt", "apple_silicon_pro")

    def test_unknown_runner_not_compatible(self):
        assert not is_compatible("nonexistent", "dgx_spark")

    def test_all_eight_runners_have_rules(self):
        expected = {
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        }
        assert set(DEFAULT_COMPATIBILITY.keys()) == expected


# --- RunnerProfile compatibility ---


@pytest.mark.asyncio
async def test_runner_profile_compatibility(session):
    runner = await runner_service.create_runner(
        session,
        name="compat-mlx",
        runner_class="mlx",
        supported_machine_classes=json.dumps(["apple_silicon_pro", "apple_silicon_mini"]),
    )
    machine_ok = await machine_service.create_profile(
        session, hostname="mac-compat-test", hardware_class="apple_silicon_pro"
    )
    machine_bad = await machine_service.create_profile(
        session, hostname="rtx-compat-test", hardware_class="rtx_desktop"
    )
    await session.commit()

    assert is_runner_compatible_with_machine(runner, machine_ok)
    assert not is_runner_compatible_with_machine(runner, machine_bad)


@pytest.mark.asyncio
async def test_runner_profile_falls_back_to_static(session):
    """Runner with no stored supported_machine_classes uses static matrix."""
    runner = await runner_service.create_runner(
        session, name="compat-ollama", runner_class="ollama"
    )
    machine = await machine_service.create_profile(
        session, hostname="dgx-compat-test", hardware_class="dgx_spark"
    )
    await session.commit()

    assert is_runner_compatible_with_machine(runner, machine)


# --- DB-backed compatible lookups ---


@pytest.mark.asyncio
async def test_get_compatible_runners_for_machine(session):
    await runner_service.create_runner(
        session,
        name="lookup-ollama",
        runner_class="ollama",
        supported_machine_classes=json.dumps(["dgx_spark", "apple_silicon_pro"]),
    )
    await runner_service.create_runner(
        session,
        name="lookup-mlx",
        runner_class="mlx",
        supported_machine_classes=json.dumps(["apple_silicon_pro"]),
    )
    await session.commit()

    compatible = await get_compatible_runners(session, "apple_silicon_pro")
    classes = {r.runner_class for r in compatible}
    assert "ollama" in classes
    assert "mlx" in classes

    compatible_dgx = await get_compatible_runners(session, "dgx_spark")
    classes_dgx = {r.runner_class for r in compatible_dgx}
    assert "ollama" in classes_dgx
    assert "mlx" not in classes_dgx


@pytest.mark.asyncio
async def test_get_compatible_machines_for_runner(session):
    await machine_service.create_profile(session, hostname="m-dgx", hardware_class="dgx_spark")
    await machine_service.create_profile(
        session, hostname="m-mac", hardware_class="apple_silicon_pro"
    )
    await machine_service.create_profile(session, hostname="m-rpi", hardware_class="edge_device")
    await session.commit()

    machines = await get_compatible_machines(session, "vllm")
    classes = {m.hardware_class for m in machines}
    assert "dgx_spark" in classes
    assert "edge_device" not in classes
    assert "apple_silicon_pro" not in classes


# --- Seed data ---


@pytest.mark.asyncio
async def test_seed_runners(session):
    created = await seed_runners(session)
    await session.commit()
    assert len(created) == 8

    runners = await runner_service.list_runners(session)
    assert len(runners) == 8
    classes = {r.runner_class for r in runners}
    assert classes == {
        "ollama",
        "lmstudio",
        "llamacpp",
        "mlx",
        "vllm",
        "sglang",
        "tensorrt",
        "openvino",
    }


@pytest.mark.asyncio
async def test_seed_runners_idempotent(session):
    await seed_runners(session)
    await session.commit()
    created_again = await seed_runners(session)
    assert len(created_again) == 0


@pytest.mark.asyncio
async def test_seed_machines(session):
    created = await seed_machines(session)
    await session.commit()
    assert len(created) == 7

    machines = await machine_service.list_profiles(session)
    assert len(machines) == 7
    classes = {m.hardware_class for m in machines}
    assert classes == {
        "dgx_spark",
        "apple_silicon_pro",
        "apple_silicon_mini",
        "rtx_desktop",
        "intel_ai_laptop",
        "old_gpu_laptop",
        "edge_device",
    }


@pytest.mark.asyncio
async def test_seed_machines_idempotent(session):
    await seed_machines(session)
    await session.commit()
    created_again = await seed_machines(session)
    assert len(created_again) == 0


@pytest.mark.asyncio
async def test_seed_all(session):
    result = await seed_all(session)
    await session.commit()
    assert result == {"runners": 8, "machines": 7, "scorers": 7, "datasets": 3}


@pytest.mark.asyncio
async def test_seeded_runners_have_metadata(session):
    await seed_runners(session)
    await session.commit()

    for seed in RUNNER_SEEDS:
        runner = await runner_service.get_runner_by_class(session, seed["runner_class"])
        assert runner is not None, f"Missing runner: {seed['runner_class']}"
        assert runner.display_name == seed["display_name"]
        assert runner.version == seed["version"]
        families = json.loads(runner.supported_model_families)
        assert len(families) > 0
        params = json.loads(runner.parameter_surface)
        assert "temperature" in params


@pytest.mark.asyncio
async def test_seeded_machines_have_metadata(session):
    await seed_machines(session)
    await session.commit()

    for seed in MACHINE_SEEDS:
        machines = await machine_service.list_profiles(
            session, hardware_class=seed["hardware_class"]
        )
        assert len(machines) >= 1, f"Missing machine: {seed['hardware_class']}"
        m = machines[0]
        assert m.cpu_description is not None
        assert m.gpu_description is not None
        assert m.ram_gb is not None


# --- Machine snapshot capture ---


@pytest.mark.asyncio
async def test_capture_machine_snapshot(session):
    machine = await machine_service.create_profile(
        session,
        hostname="snap-host",
        hardware_class="rtx_desktop",
        cpu_description="AMD Ryzen 7",
        gpu_description="RTX 4070 12 GB",
        ram_gb=32,
    )
    await session.commit()

    snap = await machine_service.capture_snapshot(
        session,
        machine.id,
        runtime_version="cuda-12.4",
        model_server_version="vllm-0.6.6",
        env_vars={"CUDA_VISIBLE_DEVICES": "0"},
        tuning_values={"gpu_memory_utilization": 0.9},
    )
    await session.commit()

    assert snap.id is not None
    data = json.loads(snap.snapshot_data)
    assert data["hostname"] == "snap-host"
    assert data["hardware_class"] == "rtx_desktop"
    assert data["ram_gb"] == 32
    assert data["runtime_version"] == "cuda-12.4"
    assert data["model_server_version"] == "vllm-0.6.6"
    assert data["env_vars"]["CUDA_VISIBLE_DEVICES"] == "0"


# --- Requested vs actual machine ---


@pytest.mark.asyncio
async def test_run_records_requested_and_actual_machine(session):
    from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion
    from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
    from ai_benchmark.eval.models.run import Run
    from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
    from ai_benchmark.eval.models.target import TargetConfiguration

    # Setup minimal eval chain
    ds = Dataset(name="reqmach-ds")
    session.add(ds)
    await session.flush()
    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=0)
    session.add(dv)
    await session.flush()

    scorer = Scorer(name="reqmach-scorer", scorer_type="exact_match")
    session.add(scorer)
    await session.flush()
    sv = ScorerVersion(scorer_id=scorer.id, version_number=1, config="{}")
    session.add(sv)
    await session.flush()

    ev = EvaluationDefinition(name="reqmach-eval")
    session.add(ev)
    await session.flush()
    evv = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": sv.id, "weight": 1.0}]),
    )
    session.add(evv)

    # Two machines: requested (DGX) and actual (RTX fallback)
    requested_machine = await machine_service.create_profile(
        session, hostname="req-dgx", hardware_class="dgx_spark"
    )
    actual_machine = await machine_service.create_profile(
        session, hostname="actual-rtx", hardware_class="rtx_desktop", ram_gb=32
    )
    await session.flush()

    actual_snap = await machine_service.capture_snapshot(session, actual_machine.id)

    target = TargetConfiguration(
        name="reqmach-target",
        model_name="llama3-8b",
        provider="ollama",
        machine_profile_id=requested_machine.id,
        inference_params="{}",
    )
    session.add(target)
    await session.flush()

    run = Run(
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        requested_machine_profile_id=requested_machine.id,
        machine_snapshot_id=actual_snap.id,
        status="completed",
        total_items=0,
    )
    session.add(run)
    await session.commit()

    assert run.requested_machine_profile_id == requested_machine.id
    assert run.machine_snapshot_id == actual_snap.id
    # The snapshot is from the actual machine, not the requested one
    snap_data = json.loads(actual_snap.snapshot_data)
    assert snap_data["hardware_class"] == "rtx_desktop"
    assert snap_data["hostname"] == "actual-rtx"


# --- Seed + compatibility integration ---


@pytest.mark.asyncio
async def test_seeded_compatibility_matrix(session):
    """After seeding, verify known compatibility relationships hold."""
    await seed_all(session)
    await session.commit()

    # MLX should only work on Apple Silicon
    mlx_runner = await runner_service.get_runner_by_class(session, "mlx")
    assert mlx_runner is not None
    mlx_machines = json.loads(mlx_runner.supported_machine_classes)
    assert set(mlx_machines) == {"apple_silicon_pro", "apple_silicon_mini"}

    # llama.cpp should support edge_device
    llamacpp_runner = await runner_service.get_runner_by_class(session, "llamacpp")
    assert llamacpp_runner is not None
    llamacpp_machines = json.loads(llamacpp_runner.supported_machine_classes)
    assert "edge_device" in llamacpp_machines

    # OpenVINO should only support Intel AI laptop
    openvino_runner = await runner_service.get_runner_by_class(session, "openvino")
    assert openvino_runner is not None
    openvino_machines = json.loads(openvino_runner.supported_machine_classes)
    assert openvino_machines == ["intel_ai_laptop"]
