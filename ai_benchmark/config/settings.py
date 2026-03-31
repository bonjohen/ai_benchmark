"""Pipeline configuration with Pydantic settings and TOML source catalog loading."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)

CONFIG_DIR = Path(__file__).parent


class PageConfig(BaseModel):
    """Configuration for a single page to poll within a source."""

    canonical_url: str
    page_type: str
    polling_frequency: str = "daily"
    css_selectors: dict[str, str] = Field(default_factory=dict)
    priority: bool = False


class SourceConfig(BaseModel):
    """Configuration for a single monitored source."""

    source_name: str
    category: str
    organization: str
    homepage_url: str
    base_domain: str
    trust_rating: float = Field(ge=1.0, le=5.0)
    source_role: str
    classification: str  # primary, secondary, discovery-only
    collection_method: str = "html"
    pages: list[PageConfig] = Field(default_factory=list)


class PipelineSettings(BaseSettings):
    """Main pipeline settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AI_BENCH_",
        env_file=os.environ.get("AI_BENCH_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///ai_benchmark.db"
    log_level: str = "INFO"
    log_format: str = "json"

    user_agent: str = "ai-benchmark-pipeline/0.1"
    request_timeout: int = 30
    max_concurrency: int = 5
    retry_attempts: int = 3
    retry_backoff_base: float = 2.0

    proxy_url: str | None = None

    github_token: str | None = None
    semantic_scholar_api_key: str | None = None

    @model_validator(mode="after")
    def _warn_relative_database_url(self) -> PipelineSettings:
        if self.database_url == "sqlite+aiosqlite:///ai_benchmark.db":
            logger.warning(
                "database_url_is_relative_default",
                hint="Set AI_BENCH_DATABASE_URL in .env or environment to an absolute path",
            )
        return self


def load_source_catalog(path: Path | None = None) -> list[SourceConfig]:
    """Load and validate the source catalog from TOML."""
    if path is None:
        path = CONFIG_DIR / "sources.toml"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    sources: list[SourceConfig] = []
    for entry in data.get("sources", []):
        pages_raw: list[dict[str, Any]] = entry.pop("pages", [])
        pages = [PageConfig(**p) for p in pages_raw]
        sources.append(SourceConfig(**entry, pages=pages))
    return sources
