"""Tests for research collectors (arXiv, HF Papers)."""

from __future__ import annotations

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.sources.research.arxiv import ArxivCollector
from ai_benchmark.sources.research.hf_papers import HFPapersCollector

ARXIV_HTML = """
<html><body>
<dd>
  <div class="list-title">Title: A New Benchmark for Language Model Evaluation</div>
  <div class="list-authors">Authors: Smith, Jones</div>
  <a href="/abs/2603.12345">Abstract</a>
</dd>
<dd>
  <div class="list-title">Title: Advances in LLM Reasoning with Claude and GPT</div>
  <div class="list-authors">Authors: Doe, Roe</div>
  <a href="/abs/2603.67890">Abstract</a>
</dd>
<dd>
  <div class="list-title">Title: Quantum Computing in Solid State Physics</div>
  <div class="list-authors">Authors: Physicist, Another</div>
  <a href="/abs/2603.99999">Abstract</a>
</dd>
</body></html>
"""

HF_PAPERS_HTML = """
<html><body>
<article>
  <h3>Scaling Laws for Language Model Agents</h3>
  <a href="/papers/2603.11111" class="paper-card"></a>
  <span class="upvote">42</span>
</article>
<article>
  <h3>Safety Alignment in Open-Weight LLMs</h3>
  <a href="/papers/2603.22222" class="paper-card"></a>
  <span class="upvote">18</span>
</article>
</body></html>
"""


def _make_source(org: str) -> SourceConfig:
    return SourceConfig(
        source_name=org,
        category="research feed",
        organization=org,
        homepage_url=f"https://{org.lower().replace(' ', '')}.org",
        base_domain=f"{org.lower().replace(' ', '')}.org",
        trust_rating=4.0,
        source_role="test",
        classification="discovery-only",
    )


# ─── arXiv collector ───


def test_arxiv_extracts_relevant_papers():
    collector = ArxivCollector(_make_source("arXiv"))
    page = PageConfig(canonical_url="https://arxiv.org/list/cs.AI/recent", page_type="recent")
    items = collector.extract_items(ARXIV_HTML, page)
    # Should extract the 2 relevant papers, filter out quantum physics
    assert len(items) == 2
    assert all(i.item_type == "candidate_paper" for i in items)


def test_arxiv_extracts_arxiv_ids():
    collector = ArxivCollector(_make_source("arXiv"))
    page = PageConfig(canonical_url="https://arxiv.org/list/cs.AI/recent", page_type="recent")
    items = collector.extract_items(ARXIV_HTML, page)
    ids = {i.metadata["arxiv_id"] for i in items}
    assert "2603.12345" in ids
    assert "2603.67890" in ids


def test_arxiv_filters_irrelevant():
    collector = ArxivCollector(_make_source("arXiv"))
    page = PageConfig(canonical_url="https://arxiv.org/list/cs.AI/recent", page_type="recent")
    items = collector.extract_items(ARXIV_HTML, page)
    titles = [i.title for i in items]
    assert not any("Quantum" in t for t in titles)


def test_arxiv_handles_empty_html():
    collector = ArxivCollector(_make_source("arXiv"))
    page = PageConfig(canonical_url="https://arxiv.org/list/cs.AI/recent", page_type="recent")
    items = collector.extract_items("<html><body></body></html>", page)
    assert items == []


# ─── HF Papers collector ───


def test_hf_papers_extracts_articles():
    collector = HFPapersCollector(_make_source("Hugging Face Papers"))
    page = PageConfig(canonical_url="https://huggingface.co/papers", page_type="papers")
    items = collector.extract_items(HF_PAPERS_HTML, page)
    assert len(items) >= 1
    assert all(i.item_type == "candidate_paper" for i in items)


def test_hf_papers_extracts_metadata():
    collector = HFPapersCollector(_make_source("Hugging Face Papers"))
    page = PageConfig(canonical_url="https://huggingface.co/papers", page_type="papers")
    items = collector.extract_items(HF_PAPERS_HTML, page)
    sources = {i.metadata.get("source") for i in items}
    assert "hf_papers" in sources


# ─── Registry integration ───


def test_research_collectors_in_registry():
    from ai_benchmark.sources.registry import COLLECTOR_CLASSES

    assert "arXiv" in COLLECTOR_CLASSES
    assert "Hugging Face Papers" in COLLECTOR_CLASSES
