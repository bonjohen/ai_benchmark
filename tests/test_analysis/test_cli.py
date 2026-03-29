"""Tests for analysis CLI commands via Click CliRunner."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from ai_benchmark.analysis.cli import analyze_group


@pytest.fixture
def cli_runner():
    """Create a Click CliRunner."""
    return CliRunner()


def test_analyze_help(cli_runner):
    """analyze --help lists subcommands."""
    result = cli_runner.invoke(analyze_group, ["--help"])
    assert result.exit_code == 0
    assert "models" in result.output
    assert "model" in result.output
    assert "benchmarks" in result.output
    assert "benchmark" in result.output
    assert "competitive" in result.output
    assert "research" in result.output
    assert "anomalies" in result.output
    assert "digest" in result.output
    assert "run-all" in result.output


def test_analyze_models_help(cli_runner):
    """analyze models --help shows options."""
    result = cli_runner.invoke(analyze_group, ["models", "--help"])
    assert result.exit_code == 0
    assert "--org" in result.output
    assert "--format" in result.output


def test_analyze_model_help(cli_runner):
    """analyze model --help shows argument and options."""
    result = cli_runner.invoke(analyze_group, ["model", "--help"])
    assert result.exit_code == 0
    assert "SLUG" in result.output
    assert "--format" in result.output


def test_analyze_benchmark_help(cli_runner):
    """analyze benchmark --help shows options."""
    result = cli_runner.invoke(analyze_group, ["benchmark", "--help"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "--format" in result.output


def test_analyze_competitive_help(cli_runner):
    """analyze competitive --help shows options."""
    result = cli_runner.invoke(analyze_group, ["competitive", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
    assert "--org" in result.output


def test_analyze_research_help(cli_runner):
    """analyze research --help shows options."""
    result = cli_runner.invoke(analyze_group, ["research", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
    assert "--format" in result.output


def test_analyze_anomalies_help(cli_runner):
    """analyze anomalies --help shows options."""
    result = cli_runner.invoke(analyze_group, ["anomalies", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
    assert "--severity" in result.output


def test_analyze_digest_help(cli_runner):
    """analyze digest --help shows options."""
    result = cli_runner.invoke(analyze_group, ["digest", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
    assert "--format" in result.output
    assert "--output" in result.output


def test_analyze_run_all_help(cli_runner):
    """analyze run-all --help shows options."""
    result = cli_runner.invoke(analyze_group, ["run-all", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
