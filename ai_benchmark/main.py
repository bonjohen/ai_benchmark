"""Application bootstrap and structured logging setup."""

from __future__ import annotations

import atexit
import sys
from datetime import datetime
from pathlib import Path

import structlog


class _TeeLogger:
    """Logger that delegates all calls to both a stdout and a file PrintLogger."""

    def __init__(self, file) -> None:  # noqa: ANN001
        self._stdout_logger = structlog.PrintLogger(sys.stdout)
        self._file_logger = structlog.PrintLogger(file)

    def __getattr__(self, name: str):  # noqa: ANN204
        def _tee(*args, **kwargs):  # noqa: ANN002, ANN003
            getattr(self._stdout_logger, name)(*args, **kwargs)
            getattr(self._file_logger, name)(*args, **kwargs)

        return _tee


class _TeeLoggerFactory:
    """Factory that produces loggers writing to both stdout and a file."""

    def __init__(self, log_dir: str) -> None:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
        self._file = (path / f"pipeline_{stamp}.log").open("a", encoding="utf-8")
        atexit.register(self._file.close)

    def __call__(self, *args) -> _TeeLogger:  # noqa: ANN002
        return _TeeLogger(self._file)


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_dir: str | None = None,
) -> None:
    """Configure structlog with JSON or console output.

    When *log_dir* is set, logs are written to both stdout and a timestamped
    file in that directory.  When ``None``, logs go to stdout only.
    """
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

    factory = _TeeLoggerFactory(log_dir) if log_dir else structlog.PrintLoggerFactory()

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=factory,
        cache_logger_on_first_use=True,
    )


async def bootstrap_pipeline():
    """Initialize the full pipeline — engine, session factory, models.

    Used by the scheduler and CLI for programmatic setup.
    """
    from .config.settings import PipelineSettings
    from .models import events, research, sources  # noqa: F401
    from .models.base import create_engine, create_session_factory

    settings = PipelineSettings()
    configure_logging(settings.log_level, settings.log_format, settings.log_dir)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    return settings, engine, session_factory
