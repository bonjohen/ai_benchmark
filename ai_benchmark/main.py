"""Application bootstrap and structured logging setup."""

from __future__ import annotations

import structlog


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog with JSON or console output."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def bootstrap_pipeline():
    """Initialize the full pipeline — engine, session factory, models.

    Used by the scheduler and CLI for programmatic setup.
    """
    from .config.settings import PipelineSettings
    from .models.base import Base, create_engine, create_session_factory
    from .models import events, research, sources  # noqa: F401

    settings = PipelineSettings()
    configure_logging(settings.log_level, settings.log_format)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    return settings, engine, session_factory
