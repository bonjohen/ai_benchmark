"""Ollama runner adapter — cross-platform baseline runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class OllamaAdapter(ModelAdapter):
    """Adapter for Ollama local inference server.

    Default endpoint: http://localhost:11434/api/chat
    Supports: /api/chat, /api/generate, /v1/chat/completions (OpenAI compat)
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("OllamaAdapter will be implemented in Phase 7")


register_adapter("ollama", OllamaAdapter)
