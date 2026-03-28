"""Local inference adapter (Ollama, vLLM, llama.cpp — OpenAI-compatible)."""

from __future__ import annotations

import time

import httpx
import structlog

from .base import GenerationResult, ModelAdapter, register_adapter

logger = structlog.get_logger()


class LocalAdapter(ModelAdapter):
    """Adapter for local inference servers using OpenAI-compatible chat format."""

    def __init__(
        self,
        *,
        endpoint_url: str = "http://localhost:11434/v1/chat/completions",
        model_name: str = "llama3",
        timeout: int = 300,
    ):
        self.endpoint_url = endpoint_url
        self.model_name = model_name
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        runtime_options = runtime_options or {}
        body = {
            "model": runtime_options.get("model", self.model_name),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        for key in ("temperature", "top_p", "max_tokens", "stop"):
            if key in inference_params:
                body[key] = inference_params[key]

        if runtime_options.get("system_prompt"):
            body["messages"].insert(0, {"role": "system", "content": runtime_options["system_prompt"]})

        timeout = runtime_options.get("timeout", self.timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            start = time.perf_counter()
            try:
                resp = await client.post(self.endpoint_url, json=body)
                latency_ms = (time.perf_counter() - start) * 1000
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
                )
            except httpx.ConnectError as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return GenerationResult(
                    output_text="",
                    latency_ms=latency_ms,
                    error=f"Connection failed (is the local server running?): {e}",
                )
            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start) * 1000
                return GenerationResult(
                    output_text="",
                    latency_ms=latency_ms,
                    error=f"Timeout after {timeout}s",
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


register_adapter("local_ollama", LocalAdapter)
register_adapter("local_vllm", LocalAdapter)
register_adapter("local_llamacpp", LocalAdapter)
