"""Shared test fixtures."""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ai_benchmark.models.base import Base, create_session_factory


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Import models to register them
    from ai_benchmark.analysis import models as analysis_models  # noqa: F401
    from ai_benchmark.eval.models import (  # noqa: F401
        artifact,
        audit,
        dataset,
        evaluation,
        machine,
        run,
        runner,
        scorer,
        target,
        trace,
    )
    from ai_benchmark.models import discovery, events, research, sources  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_engine_fk():
    """Create an in-memory SQLite engine with FK enforcement for eval tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from ai_benchmark.analysis import models as analysis_models  # noqa: F401
    from ai_benchmark.eval.models import (  # noqa: F401
        artifact,
        audit,
        dataset,
        evaluation,
        machine,
        run,
        runner,
        scorer,
        target,
        trace,
    )
    from ai_benchmark.models import discovery, events, research, sources  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Create a test database session."""
    session_factory = create_session_factory(db_engine)
    async with session_factory() as session:
        yield session
