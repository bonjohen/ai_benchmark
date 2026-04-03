"""Shared test fixtures."""

from __future__ import annotations

import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ai_benchmark.models.base import Base, create_session_factory


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Import models to register them
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


@pytest.fixture
def capture_logs():
    """Capture structlog output for assertions.

    Yields a list of dicts; each dict is one log event with keys like
    ``"event"``, ``"log_level"``, etc.
    """
    with structlog.testing.capture_logs() as logs:
        yield logs
