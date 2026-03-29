"""Phase 10 tests — Frontend foundation, navigation, search, runner/group pages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunGroup
from ai_benchmark.eval.models.runner import RunnerProfile  # noqa: F401
from ai_benchmark.eval.models.target import TargetConfiguration
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
    """Create a test app with UI routes for the test database."""
    import ai_benchmark.eval.api.app as app_module

    settings = EvalSettings()
    app = create_app(settings)

    test_factory = create_session_factory(db_engine_fk)
    original = app_module._session_factory
    app_module._session_factory = test_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app_module._session_factory = original


# ── Navigation & Page Loading ──


class TestNavigation:
    @pytest.mark.asyncio
    async def test_dashboard_loads(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert resp.status_code == 200
        assert "Evaluation Dashboard" in resp.text

    @pytest.mark.asyncio
    async def test_dashboard_has_nav_sections(self, ui_client):
        resp = await ui_client.get("/eval/")
        text = resp.text
        assert "Definitions" in text
        assert "Infrastructure" in text
        assert "Execution" in text
        assert "Analysis" in text

    @pytest.mark.asyncio
    async def test_dashboard_has_runners_link(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert "/eval/runners" in resp.text

    @pytest.mark.asyncio
    async def test_dashboard_has_run_groups_link(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert "/eval/run-groups" in resp.text

    @pytest.mark.asyncio
    async def test_dashboard_has_search(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert "/eval/search" in resp.text
        assert 'placeholder="Search..."' in resp.text

    @pytest.mark.asyncio
    async def test_dashboard_current_vs_historical(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert "Current Activity" in resp.text
        assert "Recent History" in resp.text


# ── Runner UI ──


class TestRunnerUI:
    @pytest.mark.asyncio
    async def test_runner_list_empty(self, ui_client):
        resp = await ui_client.get("/eval/runners")
        assert resp.status_code == 200
        assert "Runner Profiles" in resp.text

    @pytest.mark.asyncio
    async def test_runner_list_with_data(self, db_session, ui_client):
        runner = RunnerProfile(
            name="test-ollama-ui",
            runner_class="ollama",
            version="0.5.0",
            default_endpoint_url="http://localhost:11434",
            supported_machine_classes=json.dumps(["dgx_spark", "apple_silicon"]),
        )
        db_session.add(runner)
        await db_session.commit()

        resp = await ui_client.get("/eval/runners")
        assert resp.status_code == 200
        assert "test-ollama-ui" in resp.text
        assert "ollama" in resp.text

    @pytest.mark.asyncio
    async def test_runner_detail(self, db_session, ui_client):
        runner = RunnerProfile(
            name="test-vllm-ui",
            runner_class="vllm",
            notes="High-throughput GPU runner",
        )
        db_session.add(runner)
        await db_session.flush()
        runner_id = runner.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/runners/{runner_id}")
        assert resp.status_code == 200
        assert "test-vllm-ui" in resp.text
        assert "High-throughput GPU runner" in resp.text

    @pytest.mark.asyncio
    async def test_runner_not_found(self, ui_client):
        resp = await ui_client.get("/eval/runners/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_runner_filter_by_class(self, db_session, ui_client):
        for cls in ("ollama", "vllm"):
            db_session.add(RunnerProfile(name=f"filter-{cls}", runner_class=cls))
        await db_session.commit()

        resp = await ui_client.get("/eval/runners?runner_class=vllm")
        assert resp.status_code == 200
        assert "filter-vllm" in resp.text


# ── Run Group UI ──


class TestRunGroupUI:
    @pytest.mark.asyncio
    async def test_run_group_list_empty(self, ui_client):
        resp = await ui_client.get("/eval/run-groups")
        assert resp.status_code == 200
        assert "Run Groups" in resp.text

    @pytest.mark.asyncio
    async def test_run_group_list_with_data(self, db_session, ui_client):
        group = RunGroup(
            name="Matrix Test",
            execution_type="matrix",
            tags=json.dumps(["nightly", "regression"]),
        )
        db_session.add(group)
        await db_session.commit()

        resp = await ui_client.get("/eval/run-groups")
        assert resp.status_code == 200
        assert "Matrix Test" in resp.text
        assert "matrix" in resp.text

    @pytest.mark.asyncio
    async def test_run_group_detail(self, db_session, ui_client):
        group = RunGroup(
            name="Batch Run",
            execution_type="batch",
        )
        db_session.add(group)
        await db_session.flush()
        group_id = group.id

        # Add a child run
        ds = Dataset(name="rg-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()
        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=1)
        db_session.add(dv)
        await db_session.flush()
        ed = EvaluationDefinition(name="rg-eval", execution_mode="sequential")
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
            name="rg-tgt",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(target)
        await db_session.flush()

        run = Run(
            run_group_id=group_id,
            evaluation_version_id=ev.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
            status="completed",
            total_items=5,
            completed_items=5,
        )
        db_session.add(run)
        await db_session.commit()

        resp = await ui_client.get(f"/eval/run-groups/{group_id}")
        assert resp.status_code == 200
        assert "Batch Run" in resp.text
        assert "Runs in Group" in resp.text

    @pytest.mark.asyncio
    async def test_run_group_not_found(self, ui_client):
        resp = await ui_client.get("/eval/run-groups/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_group_filter_by_type(self, db_session, ui_client):
        for etype in ("matrix", "batch"):
            db_session.add(RunGroup(name=f"type-{etype}", execution_type=etype))
        await db_session.commit()

        resp = await ui_client.get("/eval/run-groups?execution_type=matrix")
        assert resp.status_code == 200
        assert "type-matrix" in resp.text


# ── Global Search ──


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_page_loads(self, ui_client):
        resp = await ui_client.get("/eval/search")
        assert resp.status_code == 200
        assert "Search Results" in resp.text

    @pytest.mark.asyncio
    async def test_search_no_query(self, ui_client):
        resp = await ui_client.get("/eval/search")
        assert "Enter a search term" in resp.text

    @pytest.mark.asyncio
    async def test_search_no_results(self, ui_client):
        resp = await ui_client.get("/eval/search?q=zzzznonexistent")
        assert resp.status_code == 200
        assert "No results found" in resp.text

    @pytest.mark.asyncio
    async def test_search_finds_evaluation(self, db_session, ui_client):
        ed = EvaluationDefinition(name="searchable-eval", execution_mode="sequential")
        db_session.add(ed)
        await db_session.commit()

        resp = await ui_client.get("/eval/search?q=searchable")
        assert resp.status_code == 200
        assert "searchable-eval" in resp.text
        assert "Evaluations" in resp.text

    @pytest.mark.asyncio
    async def test_search_finds_runner(self, db_session, ui_client):
        db_session.add(RunnerProfile(name="search-mlx", runner_class="mlx"))
        await db_session.commit()

        resp = await ui_client.get("/eval/search?q=mlx")
        assert resp.status_code == 200
        assert "search-mlx" in resp.text
        assert "Runners" in resp.text

    @pytest.mark.asyncio
    async def test_search_finds_target(self, db_session, ui_client):
        db_session.add(
            TargetConfiguration(
                name="search-target",
                model_name="llama3",
                provider="ollama",
                inference_params="{}",
            )
        )
        await db_session.commit()

        resp = await ui_client.get("/eval/search?q=llama3")
        assert resp.status_code == 200
        assert "search-target" in resp.text


# ── Empty State Handling ──


class TestEmptyStates:
    @pytest.mark.asyncio
    async def test_runners_empty_state(self, ui_client):
        resp = await ui_client.get("/eval/runners")
        assert resp.status_code == 200
        assert "No runner profiles registered" in resp.text

    @pytest.mark.asyncio
    async def test_run_groups_empty_state(self, ui_client):
        resp = await ui_client.get("/eval/run-groups")
        assert resp.status_code == 200
        assert "No run groups created yet" in resp.text

    @pytest.mark.asyncio
    async def test_dashboard_empty_activity(self, ui_client):
        resp = await ui_client.get("/eval/")
        assert resp.status_code == 200
        assert "No runs currently active" in resp.text


# ── Metadata Panel ──


class TestMetadataPanel:
    @pytest.mark.asyncio
    async def test_runner_detail_shows_metadata(self, db_session, ui_client):
        runner = RunnerProfile(
            name="meta-panel-runner",
            runner_class="sglang",
            supported_machine_classes=json.dumps(["dgx_spark"]),
            supported_model_families=json.dumps(["llama", "mistral"]),
        )
        db_session.add(runner)
        await db_session.flush()
        runner_id = runner.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/runners/{runner_id}")
        assert resp.status_code == 200
        assert "Compatible Machines" in resp.text
        assert "Model Families" in resp.text
        assert "dgx_spark" in resp.text
