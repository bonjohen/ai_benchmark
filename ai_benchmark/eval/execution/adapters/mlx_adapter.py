"""MLX / MLX-LM runner adapter — Apple-native runner (Metal)."""

from __future__ import annotations

from .base import AdapterCapabilities, GenerationResult, register_adapter
from .openai_compat import OpenAICompatAdapter


class MLXAdapter(OpenAICompatAdapter):
    """Adapter for MLX-LM local inference server.

    Default endpoint: http://localhost:8080
    Supports: /v1/chat/completions (OpenAI compat)
    Apple Silicon only — requires Metal acceleration.
    """

    default_endpoint = "http://localhost:8080"
    runner_name = "mlx"

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "MLXAdapter is not yet implemented. "
            "Use 'openai', 'anthropic', 'local', or 'generic_http' provider instead."
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
        )


register_adapter("mlx", MLXAdapter)
