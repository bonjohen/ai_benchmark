"""Phase 9 tests — API routes, CLI commands, authentication."""

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
from ai_benchmark.eval.models.run import Run, RunItemResult
from ai_benchmark.eval.models.runner import RunnerProfile  # noqa: F401
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.eval.models.trace import TraceReference
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# ── Runner API ──


class TestRunnerAPI:
    @pytest.fixture
    async def app_client(self, db_engine_fk):
        """Create a test app with the test database."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings()
        app = create_app(settings)

        # Override session factory to use test DB
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        app_module._session_factory = original

    @pytest.mark.asyncio
    async def test_create_and_list_runners(self, app_client):
        resp = await app_client.post(
            "/api/eval/runners",
            json={
                "name": "test-ollama",
                "runner_class": "ollama",
                "version": "0.5.0",
                "default_endpoint_url": "http://localhost:11434",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-ollama"
        assert data["runner_class"] == "ollama"

        resp = await app_client.get("/api/eval/runners")
        assert resp.status_code == 200
        runners = resp.json()
        assert len(runners) >= 1
        assert any(r["name"] == "test-ollama" for r in runners)

    @pytest.mark.asyncio
    async def test_get_runner(self, app_client):
        resp = await app_client.post(
            "/api/eval/runners",
            json={"name": "test-vllm", "runner_class": "vllm"},
        )
        runner_id = resp.json()["id"]

        resp = await app_client.get(f"/api/eval/runners/{runner_id}")
        assert resp.status_code == 200
        assert resp.json()["runner_class"] == "vllm"

    @pytest.mark.asyncio
    async def test_update_runner(self, app_client):
        resp = await app_client.post(
            "/api/eval/runners",
            json={"name": "test-mlx", "runner_class": "mlx"},
        )
        runner_id = resp.json()["id"]

        resp = await app_client.put(
            f"/api/eval/runners/{runner_id}",
            json={"version": "1.0.0", "notes": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated"

    @pytest.mark.asyncio
    async def test_runner_not_found(self, app_client):
        resp = await app_client.get("/api/eval/runners/9999")
        assert resp.status_code == 404


# ── Authentication Middleware ──


class TestAuthMiddleware:
    @pytest.mark.asyncio
    async def test_no_auth_when_key_not_set(self, db_engine_fk):
        """Auth is disabled when no API key is configured."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings()  # No api_key
        app = create_app(settings)
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/eval/runs")
            assert resp.status_code == 200

        app_module._session_factory = original

    @pytest.mark.asyncio
    async def test_auth_rejects_missing_key(self, db_engine_fk):
        """Auth rejects requests when API key is set but not provided."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings(api_key="test-secret-key")
        app = create_app(settings)
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/eval/runs")
            assert resp.status_code == 401

        app_module._session_factory = original

    @pytest.mark.asyncio
    async def test_auth_accepts_valid_key(self, db_engine_fk):
        """Auth accepts requests with valid API key."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings(api_key="test-secret-key")
        app = create_app(settings)
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/eval/runs",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200

        app_module._session_factory = original

    @pytest.mark.asyncio
    async def test_auth_accepts_bearer_token(self, db_engine_fk):
        """Auth accepts Bearer token."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings(api_key="my-secret")
        app = create_app(settings)
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/eval/runs",
                headers={"Authorization": "Bearer my-secret"},
            )
            assert resp.status_code == 200

        app_module._session_factory = original

    @pytest.mark.asyncio
    async def test_healthz_bypasses_auth(self, db_engine_fk):
        """Health check endpoint is always public."""
        import ai_benchmark.eval.api.app as app_module

        settings = EvalSettings(api_key="locked-down")
        app = create_app(settings)
        test_factory = create_session_factory(db_engine_fk)
        original = app_module._session_factory
        app_module._session_factory = test_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/healthz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

        app_module._session_factory = original


# ── Run Resume & Trace Endpoints ──


class TestRunEndpoints:
    @pytest.mark.asyncio
    async def test_resume_run(self, db_session):
        """Test resuming a failed run via service."""
        from ai_benchmark.eval.services import run_service

        ds = Dataset(name="p9-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()

        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=1)
        db_session.add(dv)
        await db_session.flush()

        ed = EvaluationDefinition(name="p9-eval", execution_mode="sequential")
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
            name="p9-tgt",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(target)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
            status="failed",
            total_items=1,
        )
        db_session.add(run)
        await db_session.flush()

        # Resume should set status back to queued
        resumed = await run_service.update_status(db_session, run.id, "queued")
        assert resumed.status == "queued"

    @pytest.mark.asyncio
    async def test_get_traces_endpoint(self, db_session):
        """Test trace retrieval via run service."""
        from ai_benchmark.eval.services import run_service

        ds = Dataset(name="p9-trace-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()

        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=1)
        db_session.add(dv)
        await db_session.flush()

        tc = TestCase(
            dataset_version_id=dv.id,
            item_index=0,
            input_text="Q",
            expected_output="A",
        )
        db_session.add(tc)
        await db_session.flush()

        ed = EvaluationDefinition(name="p9-trace-eval", execution_mode="sequential")
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
            name="p9-trace-tgt",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(target)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
            status="completed",
            total_items=1,
        )
        db_session.add(run)
        await db_session.flush()

        item = RunItemResult(
            run_id=run.id,
            test_case_id=tc.id,
            item_index=0,
            input_sent="Q",
            raw_output="A",
            scorer_results="[]",
        )
        db_session.add(item)
        await db_session.flush()

        trace = TraceReference(
            run_item_result_id=item.id,
            trace_type="token_usage",
            trace_data=json.dumps({"total_tokens": 42}),
        )
        db_session.add(trace)
        await db_session.flush()

        traces = await run_service.get_traces(db_session, item.id)
        assert len(traces) == 1
        assert traces[0].trace_type == "token_usage"


# ── Runner CLI ──


class TestRunnerCLI:
    @pytest.mark.asyncio
    async def test_runner_service_list(self, db_session):
        """Test runner listing via service."""
        from ai_benchmark.eval.services import runner_service

        await runner_service.create_runner(db_session, name="cli-ollama", runner_class="ollama")
        runners = await runner_service.list_runners(db_session)
        assert any(rr.name == "cli-ollama" for rr in runners)

    @pytest.mark.asyncio
    async def test_runner_service_get(self, db_session):
        """Test runner get by ID."""
        from ai_benchmark.eval.services import runner_service

        r = await runner_service.create_runner(db_session, name="cli-vllm", runner_class="vllm")
        got = await runner_service.get_runner(db_session, r.id)
        assert got is not None
        assert got.runner_class == "vllm"
