"""FastAPI application factory for the evaluation pipeline API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.base import Base, create_engine, create_session_factory
from ..config import EvalSettings


_session_factory = None


def get_session_factory():
    return _session_factory


async def get_session():
    """FastAPI dependency: yields an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: create engine and tables."""
    global _session_factory
    settings = app.state.settings
    db_url = getattr(settings, "database_url", "sqlite+aiosqlite:///ai_benchmark.db")
    engine = create_engine(db_url)

    # Import models to register them with Base.metadata
    from ..models import artifact, dataset, evaluation, machine, run, scorer, target  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


def create_app(settings: EvalSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""
    settings = settings or EvalSettings()

    app = FastAPI(
        title="AI Benchmark Eval API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Mount route groups
    from .routes import (
        comparisons,
        datasets,
        evaluations,
        machines,
        reports,
        runs,
        scorers,
        targets,
    )

    app.include_router(evaluations.router, prefix="/api/eval/evaluations", tags=["evaluations"])
    app.include_router(datasets.router, prefix="/api/eval/datasets", tags=["datasets"])
    app.include_router(scorers.router, prefix="/api/eval/scorers", tags=["scorers"])
    app.include_router(targets.router, prefix="/api/eval/targets", tags=["targets"])
    app.include_router(machines.router, prefix="/api/eval/machines", tags=["machines"])
    app.include_router(runs.router, prefix="/api/eval/runs", tags=["runs"])
    app.include_router(comparisons.router, prefix="/api/eval/comparisons", tags=["comparisons"])
    app.include_router(reports.router, prefix="/api/eval/reports", tags=["reports"])

    return app
