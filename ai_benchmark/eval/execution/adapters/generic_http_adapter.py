"""Generic HTTP endpoint adapter with configurable request/response mapping."""

from __future__ import annotations

import time

import httpx
import structlog

from .base import GenerationResult, ModelAdapter, register_adapter

logger = structlog.get_logger()


class GenericHTTPAdapter(ModelAdapter):
    """Adapter for arbitrary REST endpoints with configurable field mapping.

    runtime_options should include:
        request_body_template: dict with {prompt_field: "input"} etc.
        response_text_path: dot-separated path to output text (e.g., "result.text")
        headers: optional extra headers
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        model_name: str = "",
        timeout: int = 120,
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

        # Build request body from template
        template = runtime_options.get("request_body_template", {})
        prompt_field = template.get("prompt_field", "prompt")
        body = dict(template.get("base_body", {}))
        body[prompt_field] = prompt
        body.update(inference_params)

        headers = {"Content-Type": "application/json"}
        headers.update(runtime_options.get("headers", {}))

        timeout = runtime_options.get("timeout", self.timeout)
        response_path = runtime_options.get("response_text_path", "output")

        async with httpx.AsyncClient(timeout=timeout) as client:
            start = time.perf_counter()
            try:
                resp = await client.post(self.endpoint_url, json=body, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000
                resp.raise_for_status()
                data = resp.json()

                # Navigate dot-separated path to extract output text
                output = data
                for key in response_path.split("."):
                    if isinstance(output, dict):
                        output = output.get(key, "")
                    else:
                        output = ""
                        break

                return GenerationResult(
                    output_text=str(output),
                    raw_response=data,
                    latency_ms=latency_ms,
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


register_adapter("generic_http", GenericHTTPAdapter)
