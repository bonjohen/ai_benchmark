"""Phase 14 tests — Privacy, audit trails, retention controls, regression tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.audit import AuditLogEntry  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunItemResult
from ai_benchmark.eval.models.runner import RunnerProfile  # noqa: F401
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.eval.models.trace import TraceReference  # noqa: F401
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def ui_client(db_engine_fk):
    import ai_benchmark.eval.api.app as app_module

    settings = EvalSettings()
    app = create_app(settings)

    test_factory = create_session_factory(db_engine_fk)
    original = app_module._session_factory
    app_module._session_factory = test_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        yield client

    app_module._session_factory = original


@pytest.fixture
async def seed_data(db_session):
    """Seed data for privacy/audit/retention tests."""
    ds = Dataset(name="p14-ds", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
    db_session.add(dv)
    await db_session.flush()

    tc = TestCase(
        dataset_version_id=dv.id,
        item_index=0,
        input_text="Test input",
        expected_output="expected",
    )
    db_session.add(tc)
    await db_session.flush()

    ed = EvaluationDefinition(name="p14-eval", execution_mode="sequential")
    db_session.add(ed)
    await db_session.flush()

    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config="[]",
    )
    db_session.add(ev)
    await db_session.flush()

    local_target = TargetConfiguration(
        name="p14-local",
        model_name="llama3",
        provider="ollama",
        inference_params="{}",
    )
    db_session.add(local_target)
    await db_session.flush()

    remote_target = TargetConfiguration(
        name="p14-remote",
        model_name="gpt-4",
        provider="openai",
        inference_params="{}",
    )
    db_session.add(remote_target)
    await db_session.flush()

    run = Run(
        evaluation_version_id=ev.id,
        target_config_id=local_target.id,
        dataset_version_id=dv.id,
        status="completed",
        total_items=2,
        completed_items=2,
    )
    db_session.add(run)
    await db_session.flush()

    item = RunItemResult(
        run_id=run.id,
        test_case_id=tc.id,
        item_index=0,
        input_sent="Test input",
        raw_output="test output",
        overall_pass=True,
        scorer_results="[]",
        latency_ms=100.0,
    )
    db_session.add(item)
    await db_session.flush()

    trace = TraceReference(
        run_item_result_id=item.id,
        trace_type="token_usage",
        trace_data=json.dumps({"prompt_tokens": 5}),
    )
    db_session.add(trace)

    await db_session.commit()
    return {
        "ds": ds,
        "dv": dv,
        "ev": ev,
        "tc": tc,
        "local_target": local_target,
        "remote_target": remote_target,
        "run": run,
        "item": item,
    }


# ── Privacy Enforcement ──


class TestPrivacyEnforcement:
    @pytest.mark.asyncio
    async def test_local_provider_classification(self):
        from ai_benchmark.eval.services.privacy_service import is_local_provider

        assert is_local_provider("ollama") is True
        assert is_local_provider("lmstudio") is True
        assert is_local_provider("llamacpp") is True
        assert is_local_provider("mlx") is True
        assert is_local_provider("vllm") is True
        assert is_local_provider("openai") is False
        assert is_local_provider("anthropic") is False

    @pytest.mark.asyncio
    async def test_enforce_local_only_allows_local(self, db_session, seed_data):
        from ai_benchmark.eval.services.privacy_service import enforce_local_only

        violations = await enforce_local_only(
            db_session,
            target_config_id=seed_data["local_target"].id,
        )
        assert violations == []

    @pytest.mark.asyncio
    async def test_enforce_local_only_blocks_remote_dataset(self, db_session, seed_data):
        from ai_benchmark.eval.services.privacy_service import enforce_local_only

        # Mark dataset as local-only
        seed_data["ds"].is_local_only = True
        await db_session.flush()

        violations = await enforce_local_only(
            db_session,
            dataset_id=seed_data["ds"].id,
            target_config_id=seed_data["remote_target"].id,
        )
        assert len(violations) == 1
        assert "local-only" in violations[0]

    @pytest.mark.asyncio
    async def test_classify_run_privacy(self, db_session, seed_data):
        from ai_benchmark.eval.services.privacy_service import classify_run_privacy

        result = await classify_run_privacy(db_session, seed_data["run"].id)
        assert result["classification"] == "local"
        assert result["provider"] == "ollama"
        assert result["is_local_provider"] is True


# ── Audit Trails ──


class TestAuditTrails:
    @pytest.mark.asyncio
    async def test_log_data_sent(self, db_session, seed_data):
        from ai_benchmark.eval.services import audit_service

        entry = await audit_service.log_data_sent(
            db_session,
            run_id=seed_data["run"].id,
            item_index=0,
            provider="ollama",
            endpoint_url="http://localhost:11434",
            model_name="llama3",
            input_size_bytes=100,
        )
        assert entry.id is not None
        assert entry.action == "data_sent"
        assert entry.provider == "ollama"

    @pytest.mark.asyncio
    async def test_log_data_received(self, db_session, seed_data):
        from ai_benchmark.eval.services import audit_service

        entry = await audit_service.log_data_received(
            db_session,
            run_id=seed_data["run"].id,
            provider="ollama",
            output_size_bytes=50,
        )
        assert entry.action == "data_received"

    @pytest.mark.asyncio
    async def test_log_run_event(self, db_session, seed_data):
        from ai_benchmark.eval.services import audit_service

        entry = await audit_service.log_run_event(
            db_session,
            run_id=seed_data["run"].id,
            action="run_started",
            provider="ollama",
            details={"trigger": "manual"},
        )
        assert entry.action == "run_started"
        assert entry.details is not None

    @pytest.mark.asyncio
    async def test_get_audit_log(self, db_session, seed_data):
        from ai_benchmark.eval.services import audit_service

        await audit_service.log_data_sent(
            db_session,
            run_id=seed_data["run"].id,
            provider="ollama",
        )
        await audit_service.log_data_sent(
            db_session,
            run_id=seed_data["run"].id,
            provider="openai",
        )

        all_entries = await audit_service.get_audit_log(db_session)
        assert len(all_entries) >= 2

        filtered = await audit_service.get_audit_log(db_session, provider="ollama")
        assert all(e.provider == "ollama" for e in filtered)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_run(self, db_session, seed_data):
        from ai_benchmark.eval.services import audit_service

        await audit_service.log_data_sent(
            db_session,
            run_id=seed_data["run"].id,
            provider="ollama",
        )

        entries = await audit_service.get_audit_log(db_session, run_id=seed_data["run"].id)
        assert len(entries) >= 1
        assert all(e.run_id == seed_data["run"].id for e in entries)


# ── Retention Controls ──


class TestRetentionControls:
    @pytest.mark.asyncio
    async def test_cleanup_traces(self, db_session, seed_data):
        from ai_benchmark.eval.services.artifact_service import cleanup_traces

        # Traces are fresh, so none should be removed with default age
        removed = await cleanup_traces(db_session, max_age_days=90)
        assert removed == 0

    @pytest.mark.asyncio
    async def test_cleanup_raw_outputs(self, db_session, seed_data):
        from ai_benchmark.eval.services.artifact_service import cleanup_raw_outputs

        # Runs are fresh, so none should be cleaned
        cleaned = await cleanup_raw_outputs(db_session, max_age_days=90)
        assert cleaned == 0

    @pytest.mark.asyncio
    async def test_run_retention_cleanup(self, db_session, seed_data):
        from ai_benchmark.eval.services.artifact_service import run_retention_cleanup

        result = await run_retention_cleanup(db_session)
        assert "artifacts_removed" in result
        assert "traces_removed" in result
        assert "outputs_cleaned" in result

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_empty(self, db_session, seed_data):
        from ai_benchmark.eval.services.artifact_service import cleanup_artifacts

        removed = await cleanup_artifacts(db_session)
        assert removed == 0


# ── Regression Tests (Core Workflows) ──


class TestCoreWorkflowRegression:
    """End-to-end regression tests for core UI workflows."""

    @pytest.mark.asyncio
    async def test_dashboard_loads(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    @pytest.mark.asyncio
    async def test_evaluations_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/evaluations")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_datasets_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/datasets")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_targets_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/targets")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_runners_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/runners")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_machines_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/machines")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_runs_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/runs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_run_groups_list_loads(self, ui_client):
        resp = await ui_client.get("/eval/run-groups")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_loads(self, ui_client):
        resp = await ui_client.get("/eval/search")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reports_loads(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_launch_page_loads(self, ui_client):
        resp = await ui_client.get("/eval/runs/launch")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_comparison_page_loads(self, ui_client):
        resp = await ui_client.get("/eval/comparisons")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_run_detail_loads(self, db_session, seed_data, ui_client):
        run_id = seed_data["run"].id
        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "Traces" in resp.text

    @pytest.mark.asyncio
    async def test_export_json(self, ui_client):
        resp = await ui_client.get("/eval/reports/export?format=json")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_csv(self, ui_client):
        resp = await ui_client.get("/eval/reports/export?format=csv")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_markdown(self, ui_client):
        resp = await ui_client.get("/eval/reports/export?format=markdown")
        assert resp.status_code == 200
