"""llama.cpp runner adapter — portable low-level reference runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class LlamaCppAdapter(ModelAdapter):
    """Adapter for llama.cpp server (llama-server / llama-cli).

    Default endpoint: http://localhost:8080/v1/chat/completions
    OpenAI-compatible API via llama-server.
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("LlamaCppAdapter will be implemented in Phase 7")


register_adapter("llamacpp", LlamaCppAdapter)
