"""vLLM runner adapter — server-style throughput runner."""

from __future__ import annotations

from .base import AdapterCapabilities, GenerationResult, register_adapter
from .openai_compat import OpenAICompatAdapter


class VLLMAdapter(OpenAICompatAdapter):
    """Adapter for vLLM inference server.

    Default endpoint: http://localhost:8000
    Supports: /v1/chat/completions (OpenAI compat), /v1/completions
    Requires NVIDIA GPU with CUDA.
    """

    default_endpoint = "http://localhost:8000"
    runner_name = "vllm"

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "VLLMAdapter is not yet implemented. "
            "Use 'openai', 'anthropic', 'local', or 'generic_http' provider instead."
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            batch=True,
            json_mode=True,
            tool_use=True,
        )


register_adapter("vllm", VLLMAdapter)
