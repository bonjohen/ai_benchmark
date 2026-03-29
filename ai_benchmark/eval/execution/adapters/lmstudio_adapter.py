"""LM Studio runner adapter — desktop interactive runner."""

from __future__ import annotations

from .base import AdapterCapabilities, GenerationResult, register_adapter
from .openai_compat import OpenAICompatAdapter


class LMStudioAdapter(OpenAICompatAdapter):
    """Adapter for LM Studio local inference server.

    Default endpoint: http://localhost:1234
    Supports: /v1/chat/completions (OpenAI compat)
    """

    default_endpoint = "http://localhost:1234"
    runner_name = "lmstudio"

    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "LMStudioAdapter is not yet implemented. "
            "Use 'openai', 'anthropic', 'local', or 'generic_http' provider instead."
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            json_mode=True,
            vision=True,
        )


register_adapter("lmstudio", LMStudioAdapter)
