"""Tests for API key authentication middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from ai_benchmark.eval.api.app import create_app, get_session
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.models.base import Base, create_session_factory

API_KEY = "test-secret-key-12345"


async def _make_client(api_key: str | None = None):
    """Build a test app + async client with the given api_key setting."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from ai_benchmark.eval.models import (  # noqa: F401
        artifact,
        dataset,
        evaluation,
        machine,
        run,
        runner,
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

    settings = EvalSettings(api_key=api_key)
    app = create_app(settings)
    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test", follow_redirects=True)
    return client, engine


# ---------- No auth configured (lab/local mode) ----------


@pytest.mark.asyncio
async def test_no_auth_configured_allows_all():
    """When api_key is not set, requests without credentials succeed."""
    client, engine = await _make_client(api_key=None)
    try:
        resp = await client.get("/healthz")
        assert resp.status_code == 200

        resp = await client.get("/api/eval/evaluations/")
        assert resp.status_code == 200
    finally:
        await client.aclose()
        await engine.dispose()


# ---------- Auth configured ----------


@pytest.mark.asyncio
async def test_auth_configured_rejects_missing_credentials():
    """When api_key is set, requests without credentials return 401."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        resp = await client.get("/api/eval/evaluations/")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Invalid or missing API key"}
    finally:
        await client.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_auth_configured_accepts_bearer_token():
    """When api_key is set, Authorization: Bearer <key> grants access."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        resp = await client.get(
            "/api/eval/evaluations/",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
    finally:
        await client.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_auth_configured_accepts_x_api_key_header():
    """When api_key is set, X-API-Key header grants access."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        resp = await client.get(
            "/api/eval/evaluations/",
            headers={"X-API-Key": API_KEY},
        )
        assert resp.status_code == 200
    finally:
        await client.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_auth_configured_rejects_wrong_token():
    """When api_key is set, an incorrect token returns 401."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        resp = await client.get(
            "/api/eval/evaluations/",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Invalid or missing API key"}

        resp = await client.get(
            "/api/eval/evaluations/",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401
    finally:
        await client.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_healthz_always_public():
    """The /healthz endpoint bypasses auth even when api_key is configured."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    finally:
        await client.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_ui_routes_protected_when_auth_enabled():
    """UI routes require auth when api_key is configured."""
    client, engine = await _make_client(api_key=API_KEY)
    try:
        # UI dashboard would be at /eval/ — should be rejected without credentials
        resp = await client.get("/eval/")
        assert resp.status_code == 401

        # With correct key, it should not return 401
        resp = await client.get(
            "/eval/",
            headers={"X-API-Key": API_KEY},
        )
        assert resp.status_code != 401
    finally:
        await client.aclose()
        await engine.dispose()
