"""Phase 13 tests — Historical review, comparison filters, report enhancements."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunItemResult
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
async def seed_runs(db_session):
    """Seed data for run filtering and detail tests."""
    ds = Dataset(name="p13-ds", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=3)
    db_session.add(dv)
    await db_session.flush()

    tc = TestCase(
        dataset_version_id=dv.id,
        item_index=0,
        input_text="What is 2+2?",
        expected_output="4",
    )
    db_session.add(tc)
    await db_session.flush()

    ed = EvaluationDefinition(name="p13-eval", execution_mode="sequential")
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

    target = TargetConfiguration(
        name="p13-target",
        model_name="llama3",
        provider="ollama",
        inference_params="{}",
    )
    db_session.add(target)
    await db_session.flush()

    run_completed = Run(
        evaluation_version_id=ev.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="completed",
        total_items=3,
        completed_items=3,
    )
    db_session.add(run_completed)
    await db_session.flush()

    run_failed = Run(
        evaluation_version_id=ev.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="failed",
        total_items=3,
        completed_items=1,
        failed_items=2,
    )
    db_session.add(run_failed)
    await db_session.flush()

    # Add an item result with a trace
    item_result = RunItemResult(
        run_id=run_completed.id,
        test_case_id=tc.id,
        item_index=0,
        input_sent="What is 2+2?",
        raw_output="4",
        overall_pass=True,
        scorer_results="[]",
        latency_ms=150.0,
    )
    db_session.add(item_result)
    await db_session.flush()

    trace = TraceReference(
        run_item_result_id=item_result.id,
        trace_type="token_usage",
        trace_data=json.dumps({"prompt_tokens": 10, "completion_tokens": 5}),
    )
    db_session.add(trace)

    # Add metrics
    metric = RunAggregateMetric(
        run_id=run_completed.id,
        metric_name="pass_rate",
        metric_value=1.0,
    )
    db_session.add(metric)

    await db_session.commit()
    return {
        "eval": ed,
        "ev": ev,
        "target": target,
        "dv": dv,
        "run_completed": run_completed,
        "run_failed": run_failed,
        "item_result": item_result,
        "tc": tc,
    }


# ── Historical Run List Filtering ──


class TestRunListFiltering:
    @pytest.mark.asyncio
    async def test_run_list_has_filter_bar(self, ui_client):
        resp = await ui_client.get("/eval/runs")
        assert resp.status_code == 200
        assert "Filters" in resp.text
        assert "filter-status" in resp.text
        assert "filter-eval" in resp.text
        assert "filter-model" in resp.text
        assert "filter-hw" in resp.text

    @pytest.mark.asyncio
    async def test_filter_by_status(self, db_session, seed_runs, ui_client):
        resp = await ui_client.get("/eval/runs?status=completed")
        assert resp.status_code == 200
        assert "completed" in resp.text

    @pytest.mark.asyncio
    async def test_filter_by_status_failed(self, db_session, seed_runs, ui_client):
        resp = await ui_client.get("/eval/runs?status=failed")
        assert resp.status_code == 200
        assert "failed" in resp.text

    @pytest.mark.asyncio
    async def test_filter_preserves_selection(self, ui_client):
        resp = await ui_client.get("/eval/runs?status=completed")
        assert resp.status_code == 200
        assert "selected" in resp.text

    @pytest.mark.asyncio
    async def test_clear_filters_link(self, ui_client):
        resp = await ui_client.get("/eval/runs")
        assert resp.status_code == 200
        assert "Clear" in resp.text

    @pytest.mark.asyncio
    async def test_filter_by_model_name(self, db_session, seed_runs, ui_client):
        resp = await ui_client.get("/eval/runs?model_name=llama3")
        assert resp.status_code == 200


# ── Enhanced Run Detail with Traces ──


class TestRunDetailTraces:
    @pytest.mark.asyncio
    async def test_detail_has_traces_tab(self, db_session, seed_runs, ui_client):
        run_id = seed_runs["run_completed"].id
        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "tab-traces" in resp.text
        assert "Traces" in resp.text

    @pytest.mark.asyncio
    async def test_detail_shows_trace_data(self, db_session, seed_runs, ui_client):
        run_id = seed_runs["run_completed"].id
        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "token_usage" in resp.text
        assert "prompt_tokens" in resp.text

    @pytest.mark.asyncio
    async def test_detail_uses_input_sent(self, db_session, seed_runs, ui_client):
        """Verify the detail page correctly reads input_sent from RunItemResult."""
        run_id = seed_runs["run_completed"].id
        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "What is 2+2?" in resp.text

    @pytest.mark.asyncio
    async def test_detail_shows_metrics_in_summary(self, db_session, seed_runs, ui_client):
        run_id = seed_runs["run_completed"].id
        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "pass_rate" in resp.text


# ── Comparison Filters ──


class TestComparisonFilters:
    @pytest.mark.asyncio
    async def test_comparison_has_regression_filter(self, db_session, seed_runs, ui_client):
        r1 = seed_runs["run_completed"].id
        r2 = seed_runs["run_failed"].id
        resp = await ui_client.get(f"/eval/comparisons?runs={r1},{r2}")
        assert resp.status_code == 200
        assert "Regressions" in resp.text

    @pytest.mark.asyncio
    async def test_comparison_has_changed_outcomes_filter(self, db_session, seed_runs, ui_client):
        r1 = seed_runs["run_completed"].id
        r2 = seed_runs["run_failed"].id
        resp = await ui_client.get(f"/eval/comparisons?runs={r1},{r2}")
        assert resp.status_code == 200
        assert "Changed Outcomes" in resp.text

    @pytest.mark.asyncio
    async def test_comparison_data_attributes(self, db_session, seed_runs, ui_client):
        r1 = seed_runs["run_completed"].id
        r2 = seed_runs["run_failed"].id
        resp = await ui_client.get(f"/eval/comparisons?runs={r1},{r2}")
        assert resp.status_code == 200
        assert "data-regression" in resp.text


# ── Reports ──


class TestReportEnhancements:
    @pytest.mark.asyncio
    async def test_reports_page_loads(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200
        assert "Reports" in resp.text

    @pytest.mark.asyncio
    async def test_reports_has_markdown_export(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200
        assert "Export Markdown" in resp.text
        assert "format=markdown" in resp.text

    @pytest.mark.asyncio
    async def test_reports_has_runner_group_by(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200
        assert "Runner" in resp.text

    @pytest.mark.asyncio
    async def test_reports_has_tokens_metric(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200
        assert "Tokens/sec" in resp.text

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

    @pytest.mark.asyncio
    async def test_export_html(self, ui_client):
        resp = await ui_client.get("/eval/reports/export?format=html")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reports_has_presets(self, ui_client):
        resp = await ui_client.get("/eval/reports")
        assert resp.status_code == 200
        assert "Saved Presets" in resp.text
        assert "Best Coding Runs" in resp.text
