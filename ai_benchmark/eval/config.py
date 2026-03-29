"""Evaluation pipeline settings, loaded from AI_BENCH_EVAL_ environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class EvalSettings(BaseSettings):
    model_config = {"env_prefix": "AI_BENCH_EVAL_"}

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
