"""Tests for community source collectors (HF Forums, GitHub Discovery, HF Leaderboard Docs)."""

from __future__ import annotations

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.sources.community.hf_forums import HFForumsCollector
from ai_benchmark.sources.community.hf_leaderboard_docs import HFLeaderboardDocsCollector

HF_FORUMS_HTML = """
<html><body>
<tr class="topic-list-item" data-topic-id="123">
  <td><a class="title" href="/t/new-model-release/123">New Model Release Discussion</a></td>
  <td><span class="discourse-tag">models</span><span class="discourse-tag">llm</span></td>
  <td><a data-user-card="alice">alice</a></td>
  <td class="num activity"><a>15</a></td>
</tr>
<tr class="topic-list-item" data-topic-id="124">
  <td><a class="title" href="/t/benchmark-comparison/124">Benchmark Comparison Thread</a></td>
  <td><span class="discourse-tag">benchmarks</span></td>
  <td><a data-user-card="bob">bob</a></td>
  <td class="num activity"><a>8</a></td>
</tr>
</body></html>
"""

HF_LEADERBOARD_DOCS_HTML = """
<html><body>
<a href="/spaces/open-llm-leaderboard">
  <h3>Open LLM Leaderboard</h3>
  <p>Community-driven LLM evaluation</p>
</a>
<a href="/spaces/mteb-leaderboard">
  <h3>MTEB Leaderboard</h3>
  <p>Massive Text Embedding Benchmark</p>
</a>
<a href="/spaces/tiny-space">
  <h3>X</h3>
</a>
</body></html>
"""


def _make_source(org: str) -> SourceConfig:
    return SourceConfig(
        source_name=org,
        category="community",
        organization=org,
        homepage_url="https://huggingface.co",
        base_domain="huggingface.co",
        trust_rating=3.0,
        source_role="test",
        classification="discovery-only",
    )


# ─── HF Forums ───


def test_hf_forums_extracts_topics():
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_HTML, page)
    assert len(items) == 2
    assert all(i.item_type == "forum_topic" for i in items)


def test_hf_forums_extracts_tags():
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_HTML, page)
    assert "models" in items[0].metadata["tags"]
    assert "llm" in items[0].metadata["tags"]


def test_hf_forums_extracts_author():
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_HTML, page)
    assert items[0].metadata["author"] == "alice"


def test_hf_forums_minimal_body():
    """Forum topics should have empty body (minimal metadata only)."""
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_HTML, page)
    assert all(i.body == "" for i in items)


def test_hf_forums_confidence_tier():
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_HTML, page)
    assert all(i.metadata["confidence_tier"] == "low_discovery" for i in items)


# ─── HF Leaderboard Docs ───


def test_hf_leaderboard_docs_extracts_spaces():
    collector = HFLeaderboardDocsCollector(_make_source("Hugging Face Leaderboard Docs"))
    page = PageConfig(canonical_url="https://huggingface.co/docs/leaderboards", page_type="docs")
    items = collector.extract_items(HF_LEADERBOARD_DOCS_HTML, page)
    # Should extract 2 items (third has title too short: "X" < 5 chars)
    assert len(items) == 2
    assert all(i.item_type == "leaderboard_space" for i in items)


def test_hf_leaderboard_docs_extracts_urls():
    collector = HFLeaderboardDocsCollector(_make_source("Hugging Face Leaderboard Docs"))
    page = PageConfig(canonical_url="https://huggingface.co/docs/leaderboards", page_type="docs")
    items = collector.extract_items(HF_LEADERBOARD_DOCS_HTML, page)
    urls = [i.url for i in items]
    assert "/spaces/open-llm-leaderboard" in urls
    assert "/spaces/mteb-leaderboard" in urls


def test_hf_leaderboard_docs_empty():
    collector = HFLeaderboardDocsCollector(_make_source("Hugging Face Leaderboard Docs"))
    page = PageConfig(canonical_url="https://huggingface.co/docs", page_type="docs")
    items = collector.extract_items("<html><body></body></html>", page)
    assert items == []


# ─── HF Forums Support Thread Filtering ───

HF_FORUMS_MIXED_HTML = """
<html><body>
<tr class="topic-list-item" data-topic-id="200">
  <td><a class="title" href="/t/announce/200">Announcing new Llama 3.1 benchmarks</a></td>
</tr>
<tr class="topic-list-item" data-topic-id="201">
  <td><a class="title" href="/t/help/201">Please help me install transformers on Windows</a></td>
</tr>
<tr class="topic-list-item" data-topic-id="202">
  <td><a class="title" href="/t/error/202">Error analysis in LLM reasoning tasks</a></td>
</tr>
<tr class="topic-list-item" data-topic-id="203">
  <td><a class="title" href="/t/notwork/203">Tokenizer not working after upgrade</a></td>
</tr>
</body></html>
"""


def test_hf_forums_filters_support_threads():
    """Support thread titles are filtered out."""
    collector = HFForumsCollector(_make_source("Hugging Face Forums"))
    page = PageConfig(canonical_url="https://discuss.huggingface.co", page_type="forum")
    items = collector.extract_items(HF_FORUMS_MIXED_HTML, page)
    titles = [i.title for i in items]
    # Legitimate discussion topics pass through
    assert "Announcing new Llama 3.1 benchmarks" in titles
    assert "Error analysis in LLM reasoning tasks" in titles
    # Clearly support-oriented threads are filtered
    assert "Please help me install transformers on Windows" not in titles
    assert "Tokenizer not working after upgrade" not in titles
    assert len(items) == 2
