"""Tests for analysis API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from ai_benchmark.eval.api.app import create_app, get_session
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.models.base import Base, create_session_factory


@pytest.fixture
async def api_client():
    """Create an async test client with in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Import all models
    from ai_benchmark.analysis import models as analysis_models  # noqa: F401
    from ai_benchmark.eval.models import (  # noqa: F401
        artifact,
        dataset,
        evaluation,
        machine,
        run,
        scorer,
        target,
    )
    from ai_benchmark.models import discovery, events, research, sources  # noqa: F401

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


@pytest.mark.asyncio
async def test_list_models(api_client):
    """GET /api/analysis/models returns a list."""
    resp = await api_client.get("/api/analysis/models")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_model_not_found(api_client):
    """GET /api/analysis/models/<slug> returns 404 for unknown model."""
    resp = await api_client.get("/api/analysis/models/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_model_timeline_empty(api_client):
    """GET /api/analysis/models/<slug>/timeline returns empty list."""
    resp = await api_client.get("/api/analysis/models/nonexistent/timeline")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_benchmarks(api_client):
    """GET /api/analysis/benchmarks returns a list."""
    resp = await api_client.get("/api/analysis/benchmarks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_benchmark_leaderboard(api_client):
    """GET /api/analysis/benchmarks/<name> returns leaderboard structure."""
    resp = await api_client.get("/api/analysis/benchmarks/SWE-bench")
    assert resp.status_code == 200
    data = resp.json()
    assert "benchmark_name" in data
    assert "entries" in data


@pytest.mark.asyncio
async def test_get_benchmark_timeline(api_client):
    """GET /api/analysis/benchmarks/<name>/timeline returns list."""
    resp = await api_client.get("/api/analysis/benchmarks/SWE-bench/timeline")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_competitive(api_client):
    """GET /api/analysis/competitive returns timeline structure."""
    resp = await api_client.get("/api/analysis/competitive?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "window_start" in data
    assert "org_activities" in data


@pytest.mark.asyncio
async def test_get_research(api_client):
    """GET /api/analysis/research returns trends structure."""
    resp = await api_client.get("/api/analysis/research?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "window_days" in data
    assert "total_papers" in data


@pytest.mark.asyncio
async def test_get_insights(api_client):
    """GET /api/analysis/insights returns a list."""
    resp = await api_client.get("/api/analysis/insights")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_digest(api_client):
    """GET /api/analysis/digest returns digest structure."""
    resp = await api_client.get("/api/analysis/digest?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "period_start" in data
    assert "period_end" in data
    assert "stats" in data


@pytest.mark.asyncio
async def test_post_digest(api_client):
    """POST /api/analysis/digest creates and persists digest."""
    resp = await api_client.post("/api/analysis/digest?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "period_start" in data
