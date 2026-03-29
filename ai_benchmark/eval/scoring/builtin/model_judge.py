"""Model-as-judge scorer — uses a judge model to evaluate outputs."""

from __future__ import annotations

import json
import re

import structlog

# Ensure adapters are registered
from ...execution.adapters import (  # noqa: F401
    anthropic_adapter,
    generic_http_adapter,
    local_adapter,
    openai_adapter,
)
from ...execution.adapters.base import resolve_adapter
from ..base import BaseScorer, ScorerResult, register_scorer

logger = structlog.get_logger()

_DEFAULT_JUDGE_PROMPT = """You are an expert evaluator. Score the following AI output on a scale of {scale_min} to {scale_max}.

Input: {input}
Expected output: {expected}
Actual output: {output}

Evaluate the actual output against the expected output. Respond with ONLY a JSON object:
{{"score": <number>, "reasoning": "<brief explanation>"}}"""


class ModelJudgeScorer(BaseScorer):
    """Score output using a judge model.

    Config:
        judge_model: str — model name for the judge
        judge_provider: str — provider to use (default "openai")
        judge_endpoint: str | None — custom endpoint URL
        judge_api_key: str | None — API key for judge
        judge_params: dict — inference params for judge
        judge_prompt_template: str | None — custom prompt template
        scale_min: float — minimum score (default 0)
        scale_max: float — maximum score (default 5)
        pass_threshold: float — minimum to pass (default 3)
    """

    scorer_type = "model_judge"

    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        scale_min = self.config.get("scale_min", 0)
        scale_max = self.config.get("scale_max", 5)
        pass_threshold = self.config.get("pass_threshold", 3)

        provider = self.config.get("judge_provider", "openai")
        adapter_kwargs = {}
        if self.config.get("judge_endpoint"):
            adapter_kwargs["endpoint_url"] = self.config["judge_endpoint"]
        if self.config.get("judge_model"):
            adapter_kwargs["model_name"] = self.config["judge_model"]
        if self.config.get("judge_api_key"):
            adapter_kwargs["api_key"] = self.config["judge_api_key"]

        adapter = resolve_adapter(provider, **adapter_kwargs)

        template = self.config.get("judge_prompt_template") or _DEFAULT_JUDGE_PROMPT
        prompt = template.format(
            input=input_text or "",
            expected=expected or "(none)",
            output=output,
            scale_min=scale_min,
            scale_max=scale_max,
        )

        judge_params = self.config.get("judge_params", {"temperature": 0.0, "max_tokens": 256})
        result = await adapter.generate(prompt, judge_params)

        if result.error:
            logger.error("model_judge_error", error=result.error)
            return ScorerResult(
                scorer_type=self.scorer_type,
                score=0.0,
                passed=False,
                details={"error": result.error},
            )

        # Parse judge response
        raw_score, reasoning = self._parse_judge_response(result.output_text, scale_min, scale_max)

        normalized = (
            (raw_score - scale_min) / (scale_max - scale_min) if scale_max > scale_min else 0.0
        )

        return ScorerResult(
            scorer_type=self.scorer_type,
            score=normalized,
            passed=raw_score >= pass_threshold,
            details={
                "raw_score": raw_score,
                "reasoning": reasoning,
                "judge_response": result.output_text,
                "scale_min": scale_min,
                "scale_max": scale_max,
                "pass_threshold": pass_threshold,
            },
        )

    def _parse_judge_response(
        self, text: str, scale_min: float, scale_max: float
    ) -> tuple[float, str]:
        """Extract score and reasoning from judge response."""
        try:
            data = json.loads(text)
            score = float(data.get("score", scale_min))
            reasoning = data.get("reasoning", "")
            return max(scale_min, min(scale_max, score)), reasoning
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Fallback: try to find a number in the response
        numbers = re.findall(r"(\d+(?:\.\d+)?)", text)
        if numbers:
            score = float(numbers[0])
            return max(scale_min, min(scale_max, score)), text
        return scale_min, f"Could not parse judge response: {text[:200]}"


register_scorer("model_judge", ModelJudgeScorer)
