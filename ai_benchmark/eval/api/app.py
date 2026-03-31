"""FastAPI application factory for the evaluation pipeline API."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request  # noqa: TC002
from starlette.responses import JSONResponse, Response  # noqa: TC002

from ...models.base import Base, create_engine, create_session_factory
from ..config import EvalSettings

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:;"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip logging for health checks to avoid noise
        if request.url.path == "/healthz":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        await logger.ainfo(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-IP rate limiter."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._counts: dict[str, int] = {}
        self._window_start: float = time.monotonic()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks
        if request.url.path == "/healthz":
            return await call_next(request)

        now = time.monotonic()
        # Reset all counts when the window expires
        if now - self._window_start >= self.window_seconds:
            self._counts.clear()
            self._window_start = now

        client_ip = request.client.host if request.client else "unknown"
        self._counts[client_ip] = self._counts.get(client_ip, 0) + 1

        if self._counts[client_ip] > self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )

        return await call_next(request)


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
    db_url = settings.database_url
    engine = create_engine(
        db_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    # Import models to register them with Base.metadata
    from ...analysis import models as analysis_models  # noqa: F401
    from ...models import discovery  # noqa: F401
    from ...publication import models as publication_models  # noqa: F401
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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Structured access logging middleware
    app.add_middleware(AccessLoggingMiddleware)

    # Authentication middleware (active only when AI_BENCH_EVAL_API_KEY is set)
    from .middleware import APIKeyMiddleware

    app.add_middleware(APIKeyMiddleware, api_key=getattr(settings, "api_key", None))

    # Root redirect to UI dashboard
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/eval/")

    # Health check (always public)
    @app.get("/healthz", tags=["health"])
    async def healthz():
        db_status = "connected"
        factory = get_session_factory()
        if factory is not None:
            try:
                from sqlalchemy import text

                async with factory() as session:
                    await session.execute(text("SELECT 1"))
            except Exception:
                db_status = "error"
        else:
            db_status = "error"
        return {"status": "ok", "database": db_status}

    # Mount route groups
    from .routes import (
        comparisons,
        datasets,
        evaluations,
        machines,
        reports,
        runners,
        runs,
        scorers,
        targets,
    )

    app.include_router(evaluations.router, prefix="/api/eval/evaluations", tags=["evaluations"])
    app.include_router(datasets.router, prefix="/api/eval/datasets", tags=["datasets"])
    app.include_router(scorers.router, prefix="/api/eval/scorers", tags=["scorers"])
    app.include_router(targets.router, prefix="/api/eval/targets", tags=["targets"])
    app.include_router(machines.router, prefix="/api/eval/machines", tags=["machines"])
    app.include_router(runners.router, prefix="/api/eval/runners", tags=["runners"])
    app.include_router(runs.router, prefix="/api/eval/runs", tags=["runs"])
    app.include_router(comparisons.router, prefix="/api/eval/comparisons", tags=["comparisons"])
    app.include_router(reports.router, prefix="/api/eval/reports", tags=["reports"])

    # Mount analysis router
    from ...analysis.api import router as analysis_router

    app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])

    # Mount publication router
    from ...publication.api import router as publication_router

    app.include_router(publication_router, prefix="/api/publications", tags=["publications"])

    # Mount UI templates and static files
    from ..ui.server import mount_ui

    mount_ui(app)

    # Mount publication UI
    from ...publication.ui.server import mount_publication_ui

    mount_publication_ui(app)

    return app
