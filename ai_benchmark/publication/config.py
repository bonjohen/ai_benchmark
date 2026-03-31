"""Publication pipeline settings, loaded from AI_BENCH_PUB_ environment variables."""

from __future__ import annotations

import os

import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)


class PublicationSettings(BaseSettings):
    model_config = {
        "env_prefix": "AI_BENCH_PUB_",
        "env_file": os.environ.get("AI_BENCH_ENV_FILE", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    database_url: str = "sqlite+aiosqlite:///ai_benchmark.db"
    cutoff_hour: int = 6  # Hour of day (0-23) marking end of publication window
    timezone: str = "US/Pacific"
    max_items_per_section: int = 10
    min_score_threshold: float = 0.1
    include_low_confidence: bool = False
    auto_freeze_delay_hours: int = 12
    export_path: str | None = None
    archive_retention_days: int = 90
    html_mode: str = "dynamic"  # dynamic | static | both
