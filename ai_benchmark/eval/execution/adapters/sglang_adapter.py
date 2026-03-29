"""SGLang runner adapter — high-performance serving runner."""

from __future__ import annotations

from .base import AdapterCapabilities, register_adapter
from .openai_compat import OpenAICompatAdapter


class SGLangAdapter(OpenAICompatAdapter):
    """Adapter for SGLang inference server.

    Default endpoint: http://localhost:30000
    Supports: /v1/chat/completions (OpenAI compat)
    Requires NVIDIA GPU with CUDA. RadixAttention for KV-cache reuse.
    """

    default_endpoint = "http://localhost:30000"
    runner_name = "sglang"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            batch=True,
            json_mode=True,
        )


register_adapter("sglang", SGLangAdapter)
