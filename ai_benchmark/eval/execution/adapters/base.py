"""Abstract model adapter interface and GenerationResult."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class GenerationResult:
    """Result from a model generation call."""

    output_text: str
    raw_response: dict | None = None
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate_usd: float | None = None
    trace_id: str | None = None
    retry_count: int = 0
    error: str | None = None


class ModelAdapter(abc.ABC):
    """Abstract interface for calling a model endpoint."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        """Send prompt to model, return result with metadata."""
        ...


# Provider string → adapter class mapping (populated by adapter modules)
_ADAPTER_REGISTRY: dict[str, type[ModelAdapter]] = {}


def register_adapter(provider: str, cls: type[ModelAdapter]) -> None:
    _ADAPTER_REGISTRY[provider] = cls


def resolve_adapter(provider: str, **kwargs) -> ModelAdapter:
    """Instantiate the appropriate adapter for a provider string."""
    cls = _ADAPTER_REGISTRY.get(provider)
    if cls is None:
        raise ValueError(
            f"No adapter registered for provider '{provider}'. "
            f"Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return cls(**kwargs)
