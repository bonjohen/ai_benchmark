"""Phase 12 tests — Run launch, live monitoring, cancel/resume actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run
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
    """Seed minimum data for run operations."""
    ds = Dataset(name="p12-ds", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=5)
    db_session.add(dv)
    await db_session.flush()

    ed = EvaluationDefinition(name="p12-eval", execution_mode="sequential")
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
        name="p12-target",
        model_name="llama3",
        provider="ollama",
        inference_params="{}",
    )
    db_session.add(target)
    await db_session.flush()

    await db_session.commit()
    return {"eval": ed, "ev": ev, "target": target, "dv": dv}


# ── Launch Page ──


class TestRunLaunch:
    @pytest.mark.asyncio
    async def test_launch_page_loads(self, ui_client):
        resp = await ui_client.get("/eval/runs/launch")
        assert resp.status_code == 200
        assert "Launch Run" in resp.text
        assert "Quick Presets" in resp.text

    @pytest.mark.asyncio
    async def test_launch_page_shows_evaluations(self, db_session, ui_client):
        ed = EvaluationDefinition(name="launch-eval", execution_mode="sequential")
        db_session.add(ed)
        await db_session.commit()

        resp = await ui_client.get("/eval/runs/launch")
        assert resp.status_code == 200
        assert "launch-eval" in resp.text

    @pytest.mark.asyncio
    async def test_launch_page_shows_targets(self, db_session, ui_client):
        t = TargetConfiguration(
            name="launch-target",
            model_name="gpt-4",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(t)
        await db_session.commit()

        resp = await ui_client.get("/eval/runs/launch")
        assert resp.status_code == 200
        assert "launch-target" in resp.text

    @pytest.mark.asyncio
    async def test_launch_presets_visible(self, ui_client):
        resp = await ui_client.get("/eval/runs/launch")
        assert "Smoke Test" in resp.text
        assert "Full Benchmark" in resp.text
        assert "Runner Comparison" in resp.text
        assert "Machine Comparison" in resp.text

    @pytest.mark.asyncio
    async def test_runs_list_has_launch_button(self, ui_client):
        resp = await ui_client.get("/eval/runs")
        assert resp.status_code == 200
        assert "Launch Run" in resp.text
        assert "/eval/runs/launch" in resp.text


# ── Cancel / Resume ──


class TestRunActions:
    @pytest.mark.asyncio
    async def test_cancel_running_run(self, db_session, seed_data, ui_client):
        run = Run(
            evaluation_version_id=seed_data["ev"].id,
            target_config_id=seed_data["target"].id,
            dataset_version_id=seed_data["dv"].id,
            status="running",
            total_items=5,
        )
        db_session.add(run)
        await db_session.flush()
        run_id = run.id
        await db_session.commit()

        resp = await ui_client.post(f"/eval/runs/{run_id}/cancel")
        assert resp.status_code == 200
        assert "canceled" in resp.text

    @pytest.mark.asyncio
    async def test_resume_failed_run(self, db_session, seed_data, ui_client):
        run = Run(
            evaluation_version_id=seed_data["ev"].id,
            target_config_id=seed_data["target"].id,
            dataset_version_id=seed_data["dv"].id,
            status="failed",
            total_items=5,
        )
        db_session.add(run)
        await db_session.flush()
        run_id = run.id
        await db_session.commit()

        resp = await ui_client.post(f"/eval/runs/{run_id}/resume")
        assert resp.status_code == 200
        assert "queued" in resp.text

    @pytest.mark.asyncio
    async def test_live_page_shows_cancel_for_running(self, db_session, seed_data, ui_client):
        run = Run(
            evaluation_version_id=seed_data["ev"].id,
            target_config_id=seed_data["target"].id,
            dataset_version_id=seed_data["dv"].id,
            status="running",
            total_items=5,
        )
        db_session.add(run)
        await db_session.flush()
        run_id = run.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/runs/{run_id}/live")
        assert resp.status_code == 200
        assert "Cancel" in resp.text

    @pytest.mark.asyncio
    async def test_live_page_shows_resume_for_failed(self, db_session, seed_data, ui_client):
        run = Run(
            evaluation_version_id=seed_data["ev"].id,
            target_config_id=seed_data["target"].id,
            dataset_version_id=seed_data["dv"].id,
            status="failed",
            total_items=5,
        )
        db_session.add(run)
        await db_session.flush()
        run_id = run.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/runs/{run_id}/live")
        assert resp.status_code == 200
        assert "Resume" in resp.text

    @pytest.mark.asyncio
    async def test_detail_page_shows_cancel_for_queued(self, db_session, seed_data, ui_client):
        run = Run(
            evaluation_version_id=seed_data["ev"].id,
            target_config_id=seed_data["target"].id,
            dataset_version_id=seed_data["dv"].id,
            status="queued",
            total_items=5,
        )
        db_session.add(run)
        await db_session.flush()
        run_id = run.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert "Cancel" in resp.text


# ── Empty State ──


class TestRunEmptyState:
    @pytest.mark.asyncio
    async def test_runs_empty_has_launch_cta(self, ui_client):
        resp = await ui_client.get("/eval/runs")
        assert resp.status_code == 200
        assert "Launch a Run" in resp.text
