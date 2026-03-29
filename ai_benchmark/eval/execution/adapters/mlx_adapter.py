"""MLX / MLX-LM runner adapter — Apple-native runner."""

from __future__ import annotations

from .base import ModelAdapter, register_adapter


class MLXAdapter(ModelAdapter):
    """Adapter for MLX-LM on Apple Silicon.

    Uses mlx_lm.generate or mlx_lm server endpoint.
    Apple Silicon only (Metal backend).
    """

    async def generate(self, prompt, inference_params, runtime_options=None):
        raise NotImplementedError("MLXAdapter will be implemented in Phase 7")


register_adapter("mlx", MLXAdapter)
