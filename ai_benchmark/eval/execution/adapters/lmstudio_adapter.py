"""LM Studio runner adapter — desktop interactive runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class LMStudioAdapter(ModelAdapter):
    """Adapter for LM Studio local server.

    Default endpoint: http://localhost:1234/v1/chat/completions
    OpenAI-compatible API.
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("LMStudioAdapter will be implemented in Phase 7")


register_adapter("lmstudio", LMStudioAdapter)
