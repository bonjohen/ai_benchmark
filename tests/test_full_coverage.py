"""Full source coverage integration test — verify all 22 sources are registered."""

from __future__ import annotations

from ai_benchmark.sources.registry import COLLECTOR_CLASSES, list_registered_organizations


# All organizations with collectors in the registry.
# Note: Semantic Scholar is an enrichment API client (used by triage pipeline),
# not a polled collector, so it is not in the registry. 22 sources, 21 collectors.
ALL_ORGANIZATIONS = [
    # Official vendors (7)
    "OpenAI", "Anthropic", "Google", "xAI", "Mistral AI", "Cohere", "Meta",
    # Benchmarks (7)
    "Artificial Analysis", "LMArena", "LiveBench", "SWE-bench",
    "GAIA", "HLE", "Terminal-Bench",
    # Research (2 collectors — S2 is enrichment-only)
    "arXiv", "Hugging Face Papers",
    # News (2)
    "Reuters", "TechCrunch",
    # Community (3)
    "Hugging Face Forums", "GitHub", "Hugging Face Leaderboard Docs",
]


def test_all_sources_registered():
    """Every polled source from the catalog must have a registered collector."""
    registered = set(COLLECTOR_CLASSES.keys())
    for org in ALL_ORGANIZATIONS:
        assert org in registered, f"Missing collector for: {org}"


def test_collector_count():
    """Registry should contain exactly 21 collector classes (S2 is enrichment-only)."""
    assert len(COLLECTOR_CLASSES) == 21


def test_list_registered_organizations_matches():
    orgs = list_registered_organizations()
    assert set(orgs) == set(ALL_ORGANIZATIONS)


def test_all_collectors_have_extract_items():
    """Every registered collector must implement extract_items."""
    for org, cls in COLLECTOR_CLASSES.items():
        assert hasattr(cls, "extract_items"), f"{org} collector missing extract_items"
