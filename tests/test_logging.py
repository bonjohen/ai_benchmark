"""Tests for configure_logging file handler."""

from __future__ import annotations

import pytest
import structlog

from ai_benchmark.main import configure_logging


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog between tests so cached loggers don't interfere."""
    yield
    structlog.reset_defaults()


def test_configure_logging_no_log_dir_uses_print_factory():
    """Without log_dir, structlog uses PrintLoggerFactory (stdout only)."""
    configure_logging("INFO", "json")
    config = structlog.get_config()
    assert isinstance(config["logger_factory"], structlog.PrintLoggerFactory)


def test_configure_logging_with_log_dir_creates_file(tmp_path):
    """With log_dir set, a pipeline_*.log file is created."""
    configure_logging("INFO", "json", log_dir=str(tmp_path))
    # Disable caching so our fresh logger picks up the new factory
    structlog.configure(cache_logger_on_first_use=False)

    log_files = list(tmp_path.glob("pipeline_*.log"))
    assert len(log_files) == 1

    log = structlog.get_logger("test")
    log.info("test_event", key="value")

    content = log_files[0].read_text(encoding="utf-8")
    assert "test_event" in content


def test_configure_logging_with_log_dir_also_writes_stdout(tmp_path, capsys):
    """With log_dir set, logs appear on both stdout and the file."""
    configure_logging("INFO", "console", log_dir=str(tmp_path))
    structlog.configure(cache_logger_on_first_use=False)

    log = structlog.get_logger("test")
    log.info("dual_output_test")

    captured = capsys.readouterr()
    assert "dual_output_test" in captured.out

    log_files = list(tmp_path.glob("pipeline_*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "dual_output_test" in content
