"""Example custom scorer for the eval pipeline.

To use:
    1. Register via the API or directly in code
    2. Set implementation_ref to "tests.test_eval.fixtures.sample_scorer:CodeOutputScorer"
    3. Include as a scorer_version in an evaluation's scorer_config

This scorer checks if the model output contains a valid Python function definition
and optionally runs basic syntax checking.
"""

from __future__ import annotations

from ai_benchmark.eval.scoring.base import BaseScorer, ScorerResult


class CodeOutputScorer(BaseScorer):
    """Scorer that validates Python code output contains a function definition."""

    scorer_type = "code_output"

    def score(self, output: str, expected: str | None = None, **kwargs) -> ScorerResult:
        config = self.config or {}
        require_def = config.get("require_function_def", True)
        check_syntax = config.get("check_syntax", True)

        issues = []

        # Check for function definition
        if require_def and "def " not in output:
            issues.append("No function definition found")

        # Check syntax
        if check_syntax:
            try:
                compile(output, "<eval>", "exec")
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")

        passed = len(issues) == 0
        score = 1.0 if passed else 0.0

        return ScorerResult(
            scorer_name=self.name,
            score=score,
            passed=passed,
            details={"issues": issues} if issues else {},
        )
