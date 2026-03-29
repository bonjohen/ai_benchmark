"""MLX / MLX-LM runner adapter — Apple-native runner (Metal)."""

from __future__ import annotations

from .base import AdapterCapabilities, register_adapter
from .openai_compat import OpenAICompatAdapter


class MLXAdapter(OpenAICompatAdapter):
    """Adapter for MLX-LM local inference server.

    Default endpoint: http://localhost:8080
    Supports: /v1/chat/completions (OpenAI compat)
    Apple Silicon only — requires Metal acceleration.
    """

    default_endpoint = "http://localhost:8080"
    runner_name = "mlx"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
        )


register_adapter("mlx", MLXAdapter)
