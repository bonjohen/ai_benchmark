"""TensorRT-LLM runner adapter — NVIDIA-native optimized runner."""

from __future__ import annotations

from .base import AdapterCapabilities, register_adapter
from .openai_compat import OpenAICompatAdapter


class TensorRTAdapter(OpenAICompatAdapter):
    """Adapter for TensorRT-LLM inference server.

    Default endpoint: http://localhost:8000
    Supports: /v1/chat/completions (OpenAI compat)
    NVIDIA GPU only. Requires engine build step before serving.
    """

    default_endpoint = "http://localhost:8000"
    runner_name = "tensorrt"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            batch=True,
        )


register_adapter("tensorrt", TensorRTAdapter)
