"""Source collector registry — maps source names to collector classes."""

from __future__ import annotations

from ..config.settings import SourceConfig
from .anthropic import AnthropicCollector
from .base import SourceCollector
from .cohere import CohereCollector
from .google import GoogleCollector
from .meta import MetaCollector
from .mistral import MistralCollector
from .openai import OpenAICollector
from .xai import XAICollector

# Map organization names to collector classes
COLLECTOR_CLASSES: dict[str, type[SourceCollector]] = {
    "OpenAI": OpenAICollector,
    "Anthropic": AnthropicCollector,
    "Google": GoogleCollector,
    "xAI": XAICollector,
    "Mistral AI": MistralCollector,
    "Cohere": CohereCollector,
    "Meta": MetaCollector,
}


def get_collector(source_config: SourceConfig, **kwargs) -> SourceCollector:
    """Instantiate the appropriate collector for a source config."""
    cls = COLLECTOR_CLASSES.get(source_config.organization)
    if cls is None:
        raise ValueError(
            f"No collector registered for organization: {source_config.organization}"
        )
    if cls is MetaCollector:
        return cls(source_config, github_token=kwargs.get("github_token"))
    return cls(source_config)


def list_registered_organizations() -> list[str]:
    """List all organizations with registered collectors."""
    return list(COLLECTOR_CLASSES.keys())
