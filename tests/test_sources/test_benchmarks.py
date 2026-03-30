"""Tests for benchmark collectors and leaderboard extraction."""

from __future__ import annotations

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.sources.benchmarks.artificial_analysis import ArtificialAnalysisCollector
from ai_benchmark.sources.benchmarks.gaia import GAIACollector
from ai_benchmark.sources.benchmarks.hle import HLECollector
from ai_benchmark.sources.benchmarks.livebench import LiveBenchCollector
from ai_benchmark.sources.benchmarks.lmarena import LMArenaCollector
from ai_benchmark.sources.benchmarks.swebench import SWEBenchCollector
from ai_benchmark.sources.benchmarks.terminal_bench import TerminalBenchCollector

LEADERBOARD_HTML = """
<html><body>
<table>
<tr><th>Model</th><th>Score</th></tr>
<tr><td>GPT-5</td><td>92.3</td></tr>
<tr><td>Claude 4</td><td>91.1</td></tr>
<tr><td>Gemini 2.5</td><td>89.7</td></tr>
</table>
</body></html>
"""

LMARENA_LEADERBOARD_HTML = """
<html><body>
<table>
<tr><th>Rank</th><th>Model</th><th>Score</th><th>Votes</th></tr>
<tr>
  <td>1</td>
  <td><div><a href="/m/gpt-5"><span>GPT-5</span></a>
    <span>OpenAI · Proprietary</span></div></td>
  <td><span>1504</span><span>±6</span></td>
  <td>12,000</td>
</tr>
<tr>
  <td>2</td>
  <td><div><a href="/m/claude-4"><span>Claude 4</span></a>
    <span>Anthropic · Proprietary</span></div></td>
  <td><span>1486</span><span>±4</span></td>
  <td>10,500</td>
</tr>
<tr>
  <td>3</td>
  <td><div><a href="/m/gemini-2.5"><span>Gemini 2.5</span></a>
    <span>Google · Proprietary</span></div></td>
  <td><span>1450</span><span>±5</span></td>
  <td>9,000</td>
</tr>
</table>
</body></html>
"""

GAIA_ORG_HTML = """
<html><body>
<a href="/datasets/gaia-results">GAIA Results Dataset</a>
<a href="/spaces/gaia-leaderboard">GAIA Leaderboard</a>
<a href="/about">About Us</a>
</body></html>
"""

LIVEBENCH_METHODOLOGY_HTML = """
<html><body>
<h1>LiveBench Methodology</h1>
<p>Contamination-resistant evaluation using regularly updated questions...</p>
</body></html>
"""

TERMINAL_BENCH_REGISTRY_HTML = """
<html><body>
<section>Terminal-Bench Task Registry v2.1</section>
<li>file-management: Create, move, and delete files in terminal environments</li>
<li>process-control: Manage running processes and system services</li>
</body></html>
"""

SWEBENCH_VERIFIED_HTML = """
<html><body>
<table>
<tr><th>Model</th><th>Resolved</th></tr>
<tr><td>Devin</td><td>52.1</td></tr>
<tr><td>SWE-agent</td><td>45.3</td></tr>
</table>
</body></html>
"""


def _make_benchmark_source(org: str) -> SourceConfig:
    return SourceConfig(
        source_name=org,
        category="benchmark leaderboard",
        organization=org,
        homepage_url=f"https://{org.lower().replace(' ', '-')}.com",
        base_domain=f"{org.lower().replace(' ', '-')}.com",
        trust_rating=4.5,
        source_role="test",
        classification="secondary",
    )


# ─── Leaderboard extraction (shared HTML) ───


def test_artificial_analysis_leaderboard():
    collector = ArtificialAnalysisCollector(_make_benchmark_source("Artificial Analysis"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    entries = collector.extract_leaderboard(LEADERBOARD_HTML, page)
    assert len(entries) == 3
    assert entries[0].model == "GPT-5"
    assert entries[0].score == "92.3"
    assert entries[0].rank == 1
    assert entries[0].variant == "performance"


def test_artificial_analysis_methodology_extraction():
    collector = ArtificialAnalysisCollector(_make_benchmark_source("Artificial Analysis"))
    page = PageConfig(canonical_url="https://example.com/methodology", page_type="methodology")
    items = collector.extract_items(
        "<html><body><section>This is our evaluation methodology"
        " for ranking models by quality and speed.</section></body></html>",
        page,
    )
    assert len(items) > 0
    assert items[0].item_type == "methodology_description"


def test_lmarena_leaderboard():
    collector = LMArenaCollector(_make_benchmark_source("LMArena"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    entries = collector.extract_leaderboard(LMARENA_LEADERBOARD_HTML, page)
    assert len(entries) == 3
    assert entries[1].model == "Claude 4"
    assert entries[1].score == "1486"
    assert entries[1].variant == "arena_elo"


def test_livebench_leaderboard():
    collector = LiveBenchCollector(_make_benchmark_source("LiveBench"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    entries = collector.extract_leaderboard(LEADERBOARD_HTML, page)
    assert len(entries) == 3
    assert entries[2].variant == "livebench"


def test_livebench_methodology_page():
    collector = LiveBenchCollector(_make_benchmark_source("LiveBench"))
    page = PageConfig(canonical_url="https://example.com/method", page_type="methodology")
    items = collector.extract_items(LIVEBENCH_METHODOLOGY_HTML, page)
    assert len(items) == 1
    assert items[0].item_type == "methodology"


def test_hle_leaderboard():
    collector = HLECollector(_make_benchmark_source("HLE"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    entries = collector.extract_leaderboard(LEADERBOARD_HTML, page)
    assert len(entries) == 3
    assert entries[0].variant == "hle_public"
    assert "confidence intervals" in entries[0].conditions


# ─── SWE-bench variant detection ───


def test_swebench_variant_detection():
    collector = SWEBenchCollector(_make_benchmark_source("SWE-bench"))
    verified_page = PageConfig(
        canonical_url="https://swebench.com/verified", page_type="leaderboard"
    )
    entries = collector.extract_leaderboard(SWEBENCH_VERIFIED_HTML, verified_page)
    assert len(entries) == 2
    assert entries[0].variant == "verified"
    assert "contamination risk" in entries[0].conditions

    lite_page = PageConfig(canonical_url="https://swebench.com/lite", page_type="leaderboard")
    entries = collector.extract_leaderboard(SWEBENCH_VERIFIED_HTML, lite_page)
    assert entries[0].variant == "lite"


def test_swebench_unknown_variant():
    collector = SWEBenchCollector(_make_benchmark_source("SWE-bench"))
    page = PageConfig(canonical_url="https://swebench.com/main", page_type="leaderboard")
    entries = collector.extract_leaderboard(SWEBENCH_VERIFIED_HTML, page)
    assert entries[0].variant == "unknown"


# ─── GAIA org page extraction ───


def test_gaia_org_page():
    collector = GAIACollector(_make_benchmark_source("GAIA"))
    page = PageConfig(canonical_url="https://huggingface.co/gaia-benchmark", page_type="org")
    items = collector.extract_items(GAIA_ORG_HTML, page)
    assert len(items) >= 2
    assert all(i.item_type == "gaia_artifact" for i in items)


def test_gaia_leaderboard_fallback():
    collector = GAIACollector(_make_benchmark_source("GAIA"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    items = collector.extract_items(LEADERBOARD_HTML, page)
    assert len(items) == 3
    assert all(i.item_type == "benchmark_entry" for i in items)


# ─── Terminal-Bench registry ───


def test_terminal_bench_registry():
    collector = TerminalBenchCollector(_make_benchmark_source("Terminal-Bench"))
    page = PageConfig(canonical_url="https://example.com/registry", page_type="registry")
    items = collector.extract_items(TERMINAL_BENCH_REGISTRY_HTML, page)
    assert len(items) >= 2
    assert all(i.item_type == "registry_entry" for i in items)


def test_terminal_bench_leaderboard():
    collector = TerminalBenchCollector(_make_benchmark_source("Terminal-Bench"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    entries = collector.extract_leaderboard(LEADERBOARD_HTML, page)
    assert len(entries) == 3
    assert entries[0].variant == "terminal_bench"


# ─── Base class: leaderboard → RawItem conversion ───


def test_benchmark_base_extract_items_converts_entries():
    collector = LiveBenchCollector(_make_benchmark_source("LiveBench"))
    page = PageConfig(canonical_url="https://example.com/leaderboard", page_type="leaderboard")
    items = collector.extract_items(LEADERBOARD_HTML, page)
    assert len(items) == 3
    assert items[0].item_type == "benchmark_entry"
    assert "GPT-5" in items[0].title
    assert items[0].metadata["rank"] == 1


# ─── Registry integration ───


def test_benchmark_collectors_in_registry():
    from ai_benchmark.sources.registry import COLLECTOR_CLASSES

    assert "Artificial Analysis" in COLLECTOR_CLASSES
    assert "LMArena" in COLLECTOR_CLASSES
    assert "LiveBench" in COLLECTOR_CLASSES
    assert "SWE-bench" in COLLECTOR_CLASSES
    assert "GAIA" in COLLECTOR_CLASSES
    assert "HLE" in COLLECTOR_CLASSES
    assert "Terminal-Bench" in COLLECTOR_CLASSES
