"""Shared fixtures for API tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from ai_benchmark.eval.api.app import create_app, get_session
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.models.base import Base, create_session_factory


@pytest.fixture
async def app_client():
    """Create a test FastAPI app with in-memory SQLite and return an httpx client."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import models
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
