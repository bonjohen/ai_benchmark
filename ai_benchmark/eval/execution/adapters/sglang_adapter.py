"""SGLang runner adapter — high-performance serving runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class SGLangAdapter(ModelAdapter):
    """Adapter for SGLang serving framework.

    Default endpoint: http://localhost:30000/v1/chat/completions
    OpenAI-compatible API. Optimized for DGX Spark / NVIDIA GPUs.
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("SGLangAdapter will be implemented in Phase 7")


register_adapter("sglang", SGLangAdapter)
