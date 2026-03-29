"""vLLM runner adapter — server-style throughput runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class VLLMAdapter(ModelAdapter):
    """Adapter for vLLM serving (vllm serve).

    Default endpoint: http://localhost:8000/v1/chat/completions
    OpenAI-compatible API.
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("VLLMAdapter will be implemented in Phase 7")


register_adapter("vllm", VLLMAdapter)
