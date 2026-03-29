"""Ollama runner adapter — cross-platform baseline runner."""

from __future__ import annotations

from .base import AdapterCapabilities, GenerationResult, register_adapter
from .openai_compat import OpenAICompatAdapter


class OllamaAdapter(OpenAICompatAdapter):
    """Adapter for Ollama local inference server.

    Default endpoint: http://localhost:11434
    Supports: /v1/chat/completions (OpenAI compat), /api/chat, /api/generate
    """

    default_endpoint = "http://localhost:11434"
    runner_name = "ollama"

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "OllamaAdapter is not yet implemented. "
            "Use 'openai', 'anthropic', 'local', or 'generic_http' provider instead."
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            json_mode=True,
            vision=True,
            tool_use=True,
        )


register_adapter("ollama", OllamaAdapter)
