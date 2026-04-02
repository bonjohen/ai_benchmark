"""Source collector registry — maps source names to collector classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicCollector
from .benchmarks.artificial_analysis import ArtificialAnalysisCollector
from .benchmarks.gaia import GAIACollector
from .benchmarks.hle import HLECollector
from .benchmarks.livebench import LiveBenchCollector
from .benchmarks.lmarena import LMArenaCollector
from .benchmarks.swebench import SWEBenchCollector
from .benchmarks.terminal_bench import TerminalBenchCollector
from .cohere import CohereCollector
from .community.github_discovery import GitHubDiscoveryCollector
from .community.hf_forums import HFForumsCollector
from .community.hf_leaderboard_docs import HFLeaderboardDocsCollector
from .google import GoogleCollector
from .meta import MetaCollector
from .mistral import MistralCollector
from .news.reuters import ReutersCollector
from .news.techcrunch import TechCrunchCollector
from .openai import OpenAICollector
from .research.arxiv import ArxivCollector
from .research.hf_papers import HFPapersCollector
from .research.semantic_scholar import SemanticScholarCollector
from .xai import XAICollector

if TYPE_CHECKING:
    from ..config.settings import SourceConfig
    from .base import SourceCollector

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
    "SWE-bench team": SWEBenchCollector,
    "GAIA": GAIACollector,
    "GAIA benchmark": GAIACollector,
    "HLE": HLECollector,
    "Scale AI": HLECollector,
    "Terminal-Bench": TerminalBenchCollector,
    "Stanford x Laude": TerminalBenchCollector,
    # Research
    "arXiv": ArxivCollector,
    "arXiv / Cornell": ArxivCollector,
    "Hugging Face Papers": HFPapersCollector,
    "Semantic Scholar": SemanticScholarCollector,
    "Ai2": SemanticScholarCollector,
    # News
    "Reuters": ReutersCollector,
    "TechCrunch": TechCrunchCollector,
    # Community
    "Hugging Face Forums": HFForumsCollector,
    "GitHub": GitHubDiscoveryCollector,
    "Hugging Face Leaderboard Docs": HFLeaderboardDocsCollector,
    "Hugging Face": HFLeaderboardDocsCollector,
}


def get_collector(source_config: SourceConfig, **kwargs) -> SourceCollector:
    """Instantiate the appropriate collector for a source config."""
    cls = COLLECTOR_CLASSES.get(source_config.organization)
    if cls is None:
        raise ValueError(f"No collector registered for organization: {source_config.organization}")
    if cls in (MetaCollector, GitHubDiscoveryCollector):
        return cls(source_config, github_token=kwargs.get("github_token"))
    if cls is SemanticScholarCollector:
        return cls(source_config, api_key=kwargs.get("semantic_scholar_api_key"))
    return cls(source_config)


def list_registered_organizations() -> list[str]:
    """List all organizations with registered collectors."""
    return list(COLLECTOR_CLASSES.keys())
