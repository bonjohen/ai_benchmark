"""llama.cpp runner adapter — portable low-level reference runner."""

from __future__ import annotations

from .base import AdapterCapabilities, GenerationResult, register_adapter
from .openai_compat import OpenAICompatAdapter


class LlamaCppAdapter(OpenAICompatAdapter):
    """Adapter for llama-server (llama.cpp HTTP server).

    Default endpoint: http://localhost:8080
    Supports: /v1/chat/completions (OpenAI compat), /completion
    """

    default_endpoint = "http://localhost:8080"
    runner_name = "llamacpp"

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "LlamaCppAdapter is not yet implemented. "
            "Use 'openai', 'anthropic', 'local', or 'generic_http' provider instead."
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            json_mode=True,
        )


register_adapter("llamacpp", LlamaCppAdapter)
