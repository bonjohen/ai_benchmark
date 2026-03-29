"""CLI smoke tests using Click's CliRunner."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from ai_benchmark.cli import cli


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    """Use a fresh temp database for every CLI test."""
    db_path = tmp_path / "test_cli.db"
    monkeypatch.setenv("AI_BENCH_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")


def _init_and_run(*args):
    """Run init-db then execute a CLI command."""
    runner = CliRunner()
    init_result = runner.invoke(cli, ["init-db"])
    assert init_result.exit_code == 0
    return runner.invoke(cli, list(args))


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AI Benchmark Intelligence Pipeline" in result.output


def test_check_config():
    runner = CliRunner()
    result = runner.invoke(cli, ["check-config"])
    assert result.exit_code == 0
    assert "Settings OK" in result.output
    assert "Source catalog OK" in result.output


def test_init_db():
    runner = CliRunner()
    result = runner.invoke(cli, ["init-db"])
    assert result.exit_code == 0
    assert "Database initialized" in result.output


def test_status_command():
    result = _init_and_run("status")
    assert result.exit_code == 0
    assert "Source" in result.output


def test_query_command_no_results():
    """Query should run without error even with no data."""
    result = _init_and_run("query", "--limit", "5")
    assert result.exit_code == 0


def test_export_json_no_results():
    result = _init_and_run("export", "--format", "json")
    assert result.exit_code == 0
    assert "[]" in result.output


def test_collect_unknown_source():
    """Collecting from an unknown source should not crash."""
    runner = CliRunner()
    result = runner.invoke(cli, ["collect", "--source", "NonExistentOrg"])
    assert result.exit_code == 0


def test_cli_commands_registered():
    """Verify all expected commands are registered."""
    commands = list(cli.commands.keys())
    assert "init-db" in commands
    assert "check-config" in commands
    assert "collect" in commands
    assert "status" in commands
    assert "query" in commands
    assert "export" in commands
    assert "run" in commands
