"""Anthropic messages API adapter."""

from __future__ import annotations

import time

import httpx
import structlog

from .base import GenerationResult, ModelAdapter, register_adapter

logger = structlog.get_logger()


class AnthropicAdapter(ModelAdapter):
    """Adapter for the Anthropic messages API."""

    def __init__(
        self,
        *,
        endpoint_url: str = "https://api.anthropic.com/v1/messages",
        api_key: str | None = None,
        model_name: str = "claude-sonnet-4-20250514",
        timeout: int = 120,
    ):
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        runtime_options = runtime_options or {}
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        body: dict = {
            "model": runtime_options.get("model", self.model_name),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": inference_params.get("max_tokens", 4096),
        }
        for key in ("temperature", "top_p", "stop_sequences"):
            if key in inference_params:
                body[key] = inference_params[key]

        if runtime_options.get("system_prompt"):
            body["system"] = runtime_options["system_prompt"]

        timeout = runtime_options.get("timeout", self.timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            start = time.perf_counter()
            try:
                resp = await client.post(self.endpoint_url, json=body, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000
                resp.raise_for_status()
                data = resp.json()

                # Extract text from content blocks
                content_blocks = data.get("content", [])
                output_text = "".join(
                    block.get("text", "") for block in content_blocks if block.get("type") == "text"
                )

                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

                return GenerationResult(
                    output_text=output_text,
                    raw_response=data,
                    latency_ms=latency_ms,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )
            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return GenerationResult(
                    output_text="",
                    latency_ms=latency_ms,
                    error=f"HTTP {e.response.status_code}: {e.response.text[:500]}",
                )
            except httpx.RequestError as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return GenerationResult(
                    output_text="",
                    latency_ms=latency_ms,
                    error=str(e),
                )


register_adapter("anthropic", AnthropicAdapter)
