"""TensorRT-LLM runner adapter — NVIDIA-native optimized runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class TensorRTAdapter(ModelAdapter):
    """Adapter for NVIDIA TensorRT-LLM.

    Uses Triton Inference Server or TensorRT-LLM Python API.
    NVIDIA GPU only (CUDA backend).
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("TensorRTAdapter will be implemented in Phase 7")


register_adapter("tensorrt", TensorRTAdapter)
