"""Abstract model adapter interface and GenerationResult."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


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


@dataclass
class AdapterCapabilities:
    """What this adapter supports."""

    streaming: bool = False
    batch: bool = False
    embeddings: bool = False
    tool_use: bool = False
    json_mode: bool = False
    vision: bool = False


@dataclass
class RuntimeMetadata:
    """Runtime information captured at execution time."""

    adapter_class: str = ""
    runner_version: str | None = None
    endpoint_url: str | None = None
    model_loaded: str | None = None
    extra: dict = field(default_factory=dict)


class ModelAdapter(abc.ABC):
    """Abstract interface for calling a model endpoint."""

    def __init__(self, **kwargs):
        self.endpoint_url = kwargs.get("endpoint_url")
        self.model_name = kwargs.get("model_name")

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        inference_params: dict,
        runtime_options: dict | None = None,
    ) -> GenerationResult:
        """Send prompt to model, return result with metadata."""
        ...

    async def health_check(self) -> bool:
        """Check if the runner endpoint is reachable. Default: True."""
        return True

    def capabilities(self) -> AdapterCapabilities:
        """Return the adapter's supported capabilities."""
        return AdapterCapabilities()

    def get_runtime_metadata(self) -> RuntimeMetadata:
        """Capture runtime information for reproducibility."""
        return RuntimeMetadata(
            adapter_class=self.__class__.__name__,
            endpoint_url=self.endpoint_url,
            model_loaded=self.model_name,
        )


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
