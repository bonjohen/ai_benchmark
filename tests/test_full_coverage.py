"""Full source coverage integration test — verify all 22 sources are registered."""

from __future__ import annotations

from ai_benchmark.sources.registry import COLLECTOR_CLASSES, list_registered_organizations

# All organizations with collectors in the registry (22 unique collector classes).
# Includes aliases for organization names that differ between sources.toml and registry.
ALL_ORGANIZATIONS = [
    # Official vendors (7)
    "OpenAI",
    "Anthropic",
    "Google",
    "xAI",
    "Mistral AI",
    "Cohere",
    "Meta",
    # Benchmarks (7) — includes aliases from sources.toml
    "Artificial Analysis",
    "LMArena",
    "LiveBench",
    "SWE-bench",
    "SWE-bench team",
    "GAIA",
    "GAIA benchmark",
    "HLE",
    "Scale AI",
    "Terminal-Bench",
    "Stanford x Laude",
    # Research (3 collectors) — includes aliases
    "arXiv",
    "arXiv / Cornell",
    "Hugging Face Papers",
    "Semantic Scholar",
    "Ai2",
    # News (2)
    "Reuters",
    "TechCrunch",
    # Community (3) — includes aliases
    "Hugging Face Forums",
    "GitHub",
    "Hugging Face Leaderboard Docs",
    "Hugging Face",
]


def test_all_sources_registered():
    """Every polled source from the catalog must have a registered collector."""
    registered = set(COLLECTOR_CLASSES.keys())
    for org in ALL_ORGANIZATIONS:
        assert org in registered, f"Missing collector for: {org}"


def test_unique_collector_count():
    """Registry should contain exactly 22 unique collector classes."""
    unique_classes = set(COLLECTOR_CLASSES.values())
    assert len(unique_classes) == 22


def test_list_registered_organizations_matches():
    orgs = list_registered_organizations()
    assert set(orgs) == set(ALL_ORGANIZATIONS)


def test_all_collectors_have_extract_items():
    """Every registered collector must implement extract_items."""
    for org, cls in COLLECTOR_CLASSES.items():
        assert hasattr(cls, "extract_items"), f"{org} collector missing extract_items"
