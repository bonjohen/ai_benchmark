"""Source collector registry — maps source names to collector classes."""

from __future__ import annotations

from ..config.settings import SourceConfig
from .anthropic import AnthropicCollector
from .base import SourceCollector
from .benchmarks.artificial_analysis import ArtificialAnalysisCollector
from .benchmarks.gaia import GAIACollector
from .benchmarks.hle import HLECollector
from .benchmarks.livebench import LiveBenchCollector
from .benchmarks.lmarena import LMArenaCollector
from .benchmarks.swebench import SWEBenchCollector
from .benchmarks.terminal_bench import TerminalBenchCollector
from .cohere import CohereCollector
from .google import GoogleCollector
from .meta import MetaCollector
from .mistral import MistralCollector
from .openai import OpenAICollector
from .research.arxiv import ArxivCollector
from .research.hf_papers import HFPapersCollector
from .xai import XAICollector

# Map organization names to collector classes
COLLECTOR_CLASSES: dict[str, type[SourceCollector]] = {
    # Official vendors
    "OpenAI": OpenAICollector,
    "Anthropic": AnthropicCollector,
    "Google": GoogleCollector,
    "xAI": XAICollector,
    "Mistral AI": MistralCollector,
    "Cohere": CohereCollector,
    "Meta": MetaCollector,
    # Benchmarks
    "Artificial Analysis": ArtificialAnalysisCollector,
    "LMArena": LMArenaCollector,
    "LiveBench": LiveBenchCollector,
    "SWE-bench": SWEBenchCollector,
    "GAIA": GAIACollector,
    "HLE": HLECollector,
    "Terminal-Bench": TerminalBenchCollector,
    # Research
    "arXiv": ArxivCollector,
    "Hugging Face Papers": HFPapersCollector,
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
