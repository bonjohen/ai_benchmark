"""OpenAI-compatible adapter base for local runner servers."""

from __future__ import annotations

import time

import httpx

from .base import AdapterCapabilities, GenerationResult, ModelAdapter, RuntimeMetadata


class OpenAICompatAdapter(ModelAdapter):
    """Base adapter for any server exposing /v1/chat/completions.

    Subclasses set default_endpoint and runner_name; most won't need
    to override generate() at all.
    """

    default_endpoint: str = "http://localhost:8080"
    runner_name: str = "generic"
    timeout_seconds: float = 120.0

    def __init__(
        self,
        endpoint_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        super().__init__(
            endpoint_url=endpoint_url or self.default_endpoint,
            model_name=model_name,
        )
        self.api_key = api_key

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        url = f"{self.endpoint_url}/v1/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body: dict = {
            "model": self.model_name or "",
            "messages": [{"role": "user", "content": prompt}],
            **inference_params,
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            elapsed = (time.perf_counter() - start) * 1000
            return GenerationResult(
                output_text="",
                latency_ms=elapsed,
                error=f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            elapsed = (time.perf_counter() - start) * 1000
            return GenerationResult(
                output_text="",
                latency_ms=elapsed,
                error=f"Connection error: {e}",
            )

        elapsed = (time.perf_counter() - start) * 1000

        # Parse OpenAI-format response
        output_text = ""
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            output_text = message.get("content", "")

        usage = data.get("usage", {})

        return GenerationResult(
            output_text=output_text,
            raw_response=data,
            latency_ms=elapsed,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.endpoint_url}/v1/models")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            json_mode=True,
        )

    def get_runtime_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            adapter_class=self.__class__.__name__,
            runner_version=None,
            endpoint_url=self.endpoint_url,
            model_loaded=self.model_name,
            extra={"runner_name": self.runner_name},
        )
