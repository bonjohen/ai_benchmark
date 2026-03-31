"""Evaluation pipeline settings, loaded from AI_BENCH_EVAL_ environment variables."""

from __future__ import annotations

import os

import structlog
from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)


class EvalSettings(BaseSettings):
    model_config = {
        "env_prefix": "AI_BENCH_EVAL_",
        "env_file": os.environ.get("AI_BENCH_ENV_FILE", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    database_url: str = "sqlite+aiosqlite:///ai_benchmark.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8100
    artifact_storage_path: str = "artifacts"
    max_concurrent_items: int = 5
    default_execution_mode: str = "sequential"  # sequential | parallel
    run_timeout_seconds: int = 3600
    item_timeout_seconds: int = 120
    retry_failed_items: int = 2
    enable_cost_tracking: bool = True
    local_only_mode: bool = False
    artifact_retention_days: int = 90
    artifact_max_per_run: int = 20
    api_key: str | None = None  # Set to enable API auth; unset = no auth (lab mode)
    rate_limit_per_minute: int = 100
    db_pool_size: int = 5
    db_max_overflow: int = 10

    @model_validator(mode="after")
    def _warn_relative_database_url(self) -> EvalSettings:
        if self.database_url == "sqlite+aiosqlite:///ai_benchmark.db":
            logger.warning(
                "eval_database_url_is_relative_default",
                hint="Set AI_BENCH_EVAL_DATABASE_URL in .env or environment to an absolute path",
            )
        return self
