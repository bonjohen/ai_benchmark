"""Ollama runner adapter — cross-platform baseline runner."""

from __future__ import annotations

from .base import AdapterCapabilities, register_adapter
from .openai_compat import OpenAICompatAdapter


class OllamaAdapter(OpenAICompatAdapter):
    """Adapter for Ollama local inference server.

    Default endpoint: http://localhost:11434
    Supports: /v1/chat/completions (OpenAI compat), /api/chat, /api/generate
    """

    default_endpoint = "http://localhost:11434"
    runner_name = "ollama"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            json_mode=True,
            vision=True,
            tool_use=True,
        )


register_adapter("ollama", OllamaAdapter)
