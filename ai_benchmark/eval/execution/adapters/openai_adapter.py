"""OpenAI / OpenAI-compatible API adapter."""

from __future__ import annotations

import time

import httpx
import structlog

from .base import GenerationResult, ModelAdapter, register_adapter

logger = structlog.get_logger()


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI-compatible chat completions API."""

    def __init__(
        self,
        *,
        endpoint_url: str = "https://api.openai.com/v1/chat/completions",
        api_key: str | None = None,
        model_name: str = "gpt-4o",
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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": runtime_options.get("model", self.model_name),
            "messages": [{"role": "user", "content": prompt}],
        }
        # Map inference params
        for key in (
            "temperature",
            "top_p",
            "max_tokens",
            "stop",
            "presence_penalty",
            "frequency_penalty",
        ):
            if key in inference_params:
                body[key] = inference_params[key]

        # System prompt from runtime_options
        if runtime_options.get("system_prompt"):
            body["messages"].insert(
                0, {"role": "system", "content": runtime_options["system_prompt"]}
            )

        timeout = runtime_options.get("timeout", self.timeout)
        retries = runtime_options.get("retries", 2)
        retry_count = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(retries + 1):
                start = time.perf_counter()
                try:
                    resp = await client.post(self.endpoint_url, json=body, headers=headers)
                    latency_ms = (time.perf_counter() - start) * 1000

                    if resp.status_code == 429 and attempt < retries:
                        retry_count += 1
                        logger.warning("openai_rate_limit", attempt=attempt)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    choice = data["choices"][0]
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    return GenerationResult(
                        output_text=choice["message"]["content"],
                        raw_response=data,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        retry_count=retry_count,
                    )
                except httpx.HTTPStatusError as e:
                    latency_ms = (time.perf_counter() - start) * 1000
                    return GenerationResult(
                        output_text="",
                        latency_ms=latency_ms,
                        retry_count=retry_count,
                        error=f"HTTP {e.response.status_code}: {e.response.text[:500]}",
                    )
                except httpx.RequestError as e:
                    latency_ms = (time.perf_counter() - start) * 1000
                    if attempt < retries:
                        retry_count += 1
                        continue
                    return GenerationResult(
                        output_text="",
                        latency_ms=latency_ms,
                        retry_count=retry_count,
                        error=str(e),
                    )

        return GenerationResult(output_text="", error="Exhausted retries")


register_adapter("openai", OpenAIAdapter)
