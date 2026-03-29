"""OpenVINO GenAI runner adapter — Intel AI hardware runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class OpenVINOAdapter(ModelAdapter):
    """Adapter for OpenVINO GenAI on Intel AI hardware.

    Targets Intel NPU (AI Boost) and CPU/iGPU on Intel Core Ultra.
    Uses openvino_genai Python API.
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("OpenVINOAdapter will be implemented in Phase 7")


register_adapter("openvino", OpenVINOAdapter)
