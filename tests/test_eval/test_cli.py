"""CLI smoke tests for eval subcommands."""

from __future__ import annotations

from click.testing import CliRunner

from ai_benchmark.cli import cli


class TestEvalCLI:
    def test_eval_group_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "--help"])
        assert result.exit_code == 0
        assert "eval" in result.output.lower()

    def test_eval_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "run", "--help"])
        assert result.exit_code == 0
        assert "--evaluation" in result.output
        assert "--target" in result.output

    def test_eval_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "status", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output

    def test_eval_list_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "list", "--help"])
        assert result.exit_code == 0
        assert "--evaluations" in result.output
        assert "--datasets" in result.output

    def test_eval_compare_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "compare", "--help"])
        assert result.exit_code == 0
        assert "--runs" in result.output

    def test_eval_export_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "export", "--help"])
        assert result.exit_code == 0
        assert "--run" in result.output
        assert "--format" in result.output

    def test_eval_serve_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output

    def test_eval_list_requires_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["eval", "list"])
        assert "Specify at least one" in result.output
