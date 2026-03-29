"""OpenVINO GenAI runner adapter — Intel AI hardware runner (NPU)."""

from __future__ import annotations

from .base import AdapterCapabilities, register_adapter
from .openai_compat import OpenAICompatAdapter


class OpenVINOAdapter(OpenAICompatAdapter):
    """Adapter for OpenVINO GenAI inference server.

    Default endpoint: http://localhost:8000
    Supports: /v1/chat/completions (OpenAI compat)
    Intel hardware only — NPU acceleration on supported Intel Core Ultra CPUs.
    """

    default_endpoint = "http://localhost:8000"
    runner_name = "openvino"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
        )


register_adapter("openvino", OpenVINOAdapter)
