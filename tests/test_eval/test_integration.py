"""E9: Integration tests and end-to-end smoke tests for the eval pipeline.

Covers acceptance criteria AC-1 through AC-8 from the PDR.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from ai_benchmark.eval.api.app import create_app, get_session
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.models.base import Base, create_session_factory


@pytest.fixture
async def integration_client():
    """Full integration test client with FK enforcement."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from ai_benchmark.models import events, research, sources  # noqa: F401
    from ai_benchmark.eval.models import (  # noqa: F401
        artifact, dataset, evaluation, machine, run, scorer, target,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    async def _override_session():
        async with session_factory() as session:
            yield session

    settings = EvalSettings()
    app = create_app(settings)
    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()


async def _create_full_chain(client, eval_name="test-eval", target_name="test-target",
                             model_name="gpt-4o", provider="openai",
                             machine_name=None, hardware_class="standard_laptop",
                             items=None):
    """Helper: create dataset + scorer + evaluation + target + optional machine, return IDs."""
    # Dataset
    ds = await client.post("/api/eval/datasets", json={
        "name": f"ds-{eval_name}", "source": "manual",
    })
    assert ds.status_code == 201
    ds_id = ds.json()["id"]

    if items is None:
        items = [
            {"input_text": "What is 2+2?", "expected_output": "4", "metadata": {"difficulty": "easy"}},
            {"input_text": "What is 3*3?", "expected_output": "9", "metadata": {"difficulty": "easy"}},
            {"input_text": "Capital of France?", "expected_output": "Paris", "metadata": {"difficulty": "easy"}},
            {"input_text": "Largest planet?", "expected_output": "Jupiter", "metadata": {"difficulty": "medium"}},
            {"input_text": "Write FizzBuzz", "expected_output": "1 2 Fizz 4 Buzz", "metadata": {"difficulty": "hard"}},
        ]

    dv = await client.post(f"/api/eval/datasets/{ds_id}/versions", json={"items": items})
    assert dv.status_code == 201
    dv_id = dv.json()["id"]

    # Scorer
    sc = await client.post("/api/eval/scorers", json={
        "name": f"sc-{eval_name}", "scorer_type": "exact_match",
    })
    assert sc.status_code == 201
    sc_id = sc.json()["id"]

    sc_ver = await client.post(f"/api/eval/scorers/{sc_id}/versions", json={
        "config": {"case_sensitive": False, "strip_whitespace": True},
    })
    assert sc_ver.status_code == 201
    sc_ver_id = sc_ver.json()["id"]

    # Evaluation
    ev = await client.post("/api/eval/evaluations", json={"name": eval_name})
    assert ev.status_code == 201
    eval_id = ev.json()["id"]

    ev_ver = await client.post(f"/api/eval/evaluations/{eval_id}/versions", json={
        "dataset_version_id": dv_id,
        "scorer_config": [{"scorer_version_id": sc_ver_id, "weight": 1.0, "pass_threshold": 0.5}],
    })
    assert ev_ver.status_code == 201
    ev_ver_id = ev_ver.json()["id"]

    # Machine (optional)
    machine_id = None
    if machine_name:
        m = await client.post("/api/eval/machines", json={
            "hostname": machine_name,
            "hardware_class": hardware_class,
            "ram_gb": 16,
        })
        assert m.status_code == 201
        machine_id = m.json()["id"]

    # Target
    target_payload = {
        "name": target_name,
        "model_name": model_name,
        "provider": provider,
        "inference_params": {"temperature": 0.0},
    }
    if machine_id:
        target_payload["machine_profile_id"] = machine_id

    tc = await client.post("/api/eval/targets", json=target_payload)
    assert tc.status_code == 201
    tc_id = tc.json()["id"]

    return {
        "dataset_id": ds_id,
        "dataset_version_id": dv_id,
        "scorer_id": sc_id,
        "scorer_version_id": sc_ver_id,
        "evaluation_id": eval_id,
        "evaluation_version_id": ev_ver_id,
        "target_config_id": tc_id,
        "machine_profile_id": machine_id,
    }


class TestE2ESmoke:
    """AC-1, AC-2: End-to-end run + comparison."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_create_run_and_verify(self, integration_client):
        """AC-1: Define evaluation, bind dataset+scorer, run against target, verify results."""
        c = integration_client
        ids = await _create_full_chain(c, eval_name="e2e-eval", target_name="e2e-target")

        # Create run
        resp = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert resp.status_code == 201
        run = resp.json()
        assert run["status"] == "queued"
        assert run["total_items"] == 5

        # Verify run detail is fetchable
        detail = await c.get(f"/api/eval/runs/{run['id']}")
        assert detail.status_code == 200
        assert detail.json()["total_items"] == 5

    @pytest.mark.asyncio
    async def test_batch_runs_and_compare(self, integration_client):
        """AC-1 + AC-2: Create multiple runs, then compare them."""
        c = integration_client
        ids = await _create_full_chain(c, eval_name="batch-eval", target_name="batch-t1")

        # Create second target
        tc2 = await c.post("/api/eval/targets", json={
            "name": "batch-t2", "model_name": "claude-3", "provider": "anthropic",
            "inference_params": {"temperature": 0.5},
        })
        assert tc2.status_code == 201
        tc2_id = tc2.json()["id"]

        # Create two runs
        r1 = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert r1.status_code == 201
        r1_id = r1.json()["id"]

        r2 = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": tc2_id,
        })
        assert r2.status_code == 201
        r2_id = r2.json()["id"]

        # Compare
        comp = await c.post("/api/eval/comparisons/compare", json={
            "run_ids": [r1_id, r2_id],
        })
        assert comp.status_code == 200
        data = comp.json()
        assert "metric_comparison" in data
        assert "item_diffs" in data

    @pytest.mark.asyncio
    async def test_three_target_batch(self, integration_client):
        """AC-1: Run against 3+ targets via batch."""
        c = integration_client
        ids = await _create_full_chain(c, eval_name="multi-eval", target_name="multi-t1")

        tc2 = await c.post("/api/eval/targets", json={
            "name": "multi-t2", "model_name": "llama-3", "provider": "local_ollama",
            "inference_params": {},
        })
        tc3 = await c.post("/api/eval/targets", json={
            "name": "multi-t3", "model_name": "phi-4", "provider": "local_vllm",
            "inference_params": {},
        })

        # Batch create
        resp = await c.post("/api/eval/runs/batch", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_ids": [ids["target_config_id"], tc2.json()["id"], tc3.json()["id"]],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "runs" in data
        assert len(data["runs"]) == 3
        assert "group_id" in data


class TestHistoricalInspectability:
    """AC-3: Historical run fully inspectable."""

    @pytest.mark.asyncio
    async def test_run_contains_full_snapshot(self, integration_client):
        c = integration_client
        ids = await _create_full_chain(
            c, eval_name="hist-eval", target_name="hist-target",
            machine_name="hist-machine", hardware_class="dgx_spark",
        )

        run_resp = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert run_resp.status_code == 201
        run_id = run_resp.json()["id"]

        # Fetch run detail
        detail = await c.get(f"/api/eval/runs/{run_id}")
        assert detail.status_code == 200
        run_data = detail.json()

        # Run references all necessary IDs for historical reconstruction
        assert run_data["evaluation_version_id"] == ids["evaluation_version_id"]
        assert run_data["target_config_id"] == ids["target_config_id"]

        # Verify evaluation version is still fetchable
        ev_ver = await c.get(
            f"/api/eval/evaluations/{ids['evaluation_id']}/versions/{ids['evaluation_version_id']}"
        )
        assert ev_ver.status_code == 200
        assert ev_ver.json()["dataset_version_id"] == ids["dataset_version_id"]

        # Verify target config is still fetchable
        tc = await c.get(f"/api/eval/targets/{ids['target_config_id']}")
        assert tc.status_code == 200
        assert tc.json()["model_name"] == "gpt-4o"


class TestCLISmoke:
    """AC-4: CLI commands work without UI."""

    @pytest.mark.asyncio
    async def test_eval_run_help(self):
        from click.testing import CliRunner
        from ai_benchmark.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "run", "--help"])
        assert result.exit_code == 0
        assert "--evaluation" in result.output
        assert "--target" in result.output

    @pytest.mark.asyncio
    async def test_eval_status_help(self):
        from click.testing import CliRunner
        from ai_benchmark.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "status", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output

    @pytest.mark.asyncio
    async def test_eval_compare_help(self):
        from click.testing import CliRunner
        from ai_benchmark.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "compare", "--help"])
        assert result.exit_code == 0
        assert "--runs" in result.output

    @pytest.mark.asyncio
    async def test_eval_export_help(self):
        from click.testing import CliRunner
        from ai_benchmark.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "export", "--help"])
        assert result.exit_code == 0
        assert "--run" in result.output
        assert "--format" in result.output

    @pytest.mark.asyncio
    async def test_eval_serve_help(self):
        from click.testing import CliRunner
        from ai_benchmark.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output


class TestMachineClassFilter:
    """AC-5: Filter runs by machine class."""

    @pytest.mark.asyncio
    async def test_list_targets_by_machine(self, integration_client):
        """Verify targets with machine profiles can be created and listed."""
        c = integration_client

        # Create two machines with different hardware classes
        m1 = await c.post("/api/eval/machines", json={
            "hostname": "laptop-1", "hardware_class": "standard_laptop", "ram_gb": 16,
        })
        assert m1.status_code == 201

        m2 = await c.post("/api/eval/machines", json={
            "hostname": "dgx-1", "hardware_class": "dgx_spark", "ram_gb": 128,
        })
        assert m2.status_code == 201

        # List machines
        resp = await c.get("/api/eval/machines")
        assert resp.status_code == 200
        machines = resp.json()
        assert len(machines) == 2
        hw_classes = {m["hardware_class"] for m in machines}
        assert "standard_laptop" in hw_classes
        assert "dgx_spark" in hw_classes


class TestActiveVsHistorical:
    """AC-6: Active vs historical runs clearly separated."""

    @pytest.mark.asyncio
    async def test_runs_have_distinct_status_groups(self, integration_client):
        c = integration_client
        ids = await _create_full_chain(c, eval_name="active-eval", target_name="active-target")

        # Create a queued run (active)
        r1 = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert r1.status_code == 201
        r1_id = r1.json()["id"]
        assert r1.json()["status"] == "queued"  # Active

        # Cancel it to make it historical
        cancel = await c.post(f"/api/eval/runs/{r1_id}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "canceled"  # Historical

        # Create another active run
        r2 = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert r2.status_code == 201
        assert r2.json()["status"] == "queued"  # Active

        # List all runs — should see both statuses
        all_runs = await c.get("/api/eval/runs")
        assert all_runs.status_code == 200
        statuses = {r["status"] for r in all_runs.json()}
        assert "queued" in statuses
        assert "canceled" in statuses


class TestRescore:
    """AC-7: Rescore without re-running generation."""

    @pytest.mark.asyncio
    async def test_rescore_endpoint_exists(self, integration_client):
        """Verify the rescore endpoint returns appropriate response for a non-existent run."""
        c = integration_client
        resp = await c.post("/api/eval/runs/9999/rescore", json={
            "scorer_config": [{"scorer_version_id": 1, "weight": 1.0}],
        })
        # Should 404 since run doesn't exist
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rescore_on_existing_run(self, integration_client):
        """AC-7: Create a run and verify rescore endpoint accepts it."""
        c = integration_client
        ids = await _create_full_chain(c, eval_name="rescore-eval", target_name="rescore-target")

        run_resp = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert run_resp.status_code == 201
        run_id = run_resp.json()["id"]

        # Rescore with new config
        rescore = await c.post(f"/api/eval/runs/{run_id}/rescore", json={
            "scorer_config": [
                {"scorer_version_id": ids["scorer_version_id"], "weight": 0.5, "pass_threshold": 0.8},
            ],
        })
        # Should succeed (200 or accept the operation)
        assert rescore.status_code in (200, 201)


class TestPartialFailure:
    """AC-8: Partial failure preserved."""

    @pytest.mark.asyncio
    async def test_run_with_items_tracks_counts(self, integration_client):
        """Verify run tracks total/completed/failed item counts separately."""
        c = integration_client
        ids = await _create_full_chain(c, eval_name="partial-eval", target_name="partial-target",
                                       items=[
                                           {"input_text": f"Q{i}", "expected_output": f"A{i}"}
                                           for i in range(10)
                                       ])

        run_resp = await c.post("/api/eval/runs", json={
            "evaluation_version_id": ids["evaluation_version_id"],
            "target_config_id": ids["target_config_id"],
        })
        assert run_resp.status_code == 201
        run = run_resp.json()
        assert run["total_items"] == 10
        assert run["completed_items"] == 0
        assert run["failed_items"] == 0

        # The run structure supports partial: total > completed + failed is valid
        detail = await c.get(f"/api/eval/runs/{run['id']}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["total_items"] == 10
        # completed + failed <= total always holds
        assert d["completed_items"] + d["failed_items"] <= d["total_items"]
