"""Authentication middleware for the eval API.

Supports API key authentication via the `X-API-Key` header or `Authorization: Bearer <key>`.
When `AI_BENCH_EVAL_API_KEY` is not set, authentication is disabled (lab/local use).
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates API key if configured. Skips auth when no key is set."""

    # Paths that never require auth
    PUBLIC_PATHS = frozenset(
        {
            "/docs",
            "/openapi.json",
            "/redoc",
            "/healthz",
        }
    )

    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self.api_key = api_key or os.environ.get("AI_BENCH_EVAL_API_KEY")

    async def dispatch(self, request: Request, call_next):
        # No key configured — auth disabled (local/lab mode)
        if not self.api_key:
            return await call_next(request)

        # Public paths bypass auth
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Static assets and UI pages bypass auth (served behind same origin)
        if request.url.path.startswith("/eval/static"):
            return await call_next(request)

        # Check X-API-Key header
        provided = request.headers.get("X-API-Key")
        if not provided:
            # Check Authorization: Bearer
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                provided = auth_header[7:]

        if provided != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
