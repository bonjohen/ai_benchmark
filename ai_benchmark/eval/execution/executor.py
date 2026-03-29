"""Item-level executor — sends a single test case to a model adapter."""

from __future__ import annotations


import structlog

from ..models.run import RunItemResult
from .adapters.base import GenerationResult, resolve_adapter

logger = structlog.get_logger()

# Ensure all adapters are registered
from .adapters import (  # noqa: F401, E402
    anthropic_adapter,
    generic_http_adapter,
    local_adapter,
    openai_adapter,
)
from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..models.dataset import TestCase


class ItemExecutor:
    """Executes a single test case against a target configuration."""

    def __init__(
        self,
        *,
        provider: str,
        endpoint_url: str | None = None,
        model_name: str = "",
        api_key: str | None = None,
        inference_params: dict | None = None,
        runtime_options: dict | None = None,
        prompt_template: str | None = None,
        prompt_wrapper: str | None = None,
        item_timeout: int = 120,
        max_retries: int = 2,
    ):
        self.provider = provider
        self.endpoint_url = endpoint_url
        self.model_name = model_name
        self.api_key = api_key
        self.inference_params = inference_params or {}
        self.runtime_options = runtime_options or {}
        self.prompt_template = prompt_template
        self.prompt_wrapper = prompt_wrapper
        self.item_timeout = item_timeout
        self.max_retries = max_retries

    def _build_prompt(self, test_case: TestCase) -> str:
        """Apply prompt_wrapper and prompt_template to the test case input."""
        prompt = test_case.input_text

        if self.prompt_template:
            prompt = self.prompt_template.replace("{{input}}", prompt)
            if test_case.context:
                prompt = prompt.replace("{{context}}", test_case.context)
            if test_case.expected_output:
                prompt = prompt.replace("{{expected}}", test_case.expected_output)

        if self.prompt_wrapper:
            prompt = self.prompt_wrapper.replace("{{prompt}}", prompt)

        return prompt

    async def execute_item(
        self,
        session: AsyncSession,
        run_id: int,
        test_case: TestCase,
        item_index: int,
    ) -> RunItemResult:
        """Execute a single test case and store the result."""
        prompt = self._build_prompt(test_case)

        # Build adapter kwargs
        adapter_kwargs: dict = {}
        if self.endpoint_url:
            adapter_kwargs["endpoint_url"] = self.endpoint_url
        if self.model_name:
            adapter_kwargs["model_name"] = self.model_name
        if self.api_key:
            adapter_kwargs["api_key"] = self.api_key
        if self.item_timeout:
            adapter_kwargs["timeout"] = self.item_timeout

        adapter = resolve_adapter(self.provider, **adapter_kwargs)

        # Execute with retry
        result: GenerationResult | None = None
        for attempt in range(self.max_retries + 1):
            result = await adapter.generate(prompt, self.inference_params, self.runtime_options)
            if result.error is None:
                break
            result.retry_count = attempt

        from datetime import datetime, timezone

        item_result = RunItemResult(
            run_id=run_id,
            test_case_id=test_case.id,
            item_index=item_index,
            input_sent=prompt,
            raw_output=result.output_text if result else "",
            scorer_results="[]",  # Populated during scoring phase
            overall_pass=None,
            error_message=result.error if result else "No result",
            latency_ms=result.latency_ms if result else 0,
            prompt_tokens=result.prompt_tokens if result else 0,
            completion_tokens=result.completion_tokens if result else 0,
            total_tokens=result.total_tokens if result else 0,
            cost_estimate_usd=result.cost_estimate_usd if result else None,
            retry_count=result.retry_count if result else 0,
            trace_id=result.trace_id if result else None,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(item_result)
        await session.flush()
        return item_result
