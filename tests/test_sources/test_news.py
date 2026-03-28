"""Tests for news source collectors (Reuters, TechCrunch)."""

from __future__ import annotations

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.sources.news.reuters import ReutersCollector
from ai_benchmark.sources.news.techcrunch import TechCrunchCollector


REUTERS_HTML = """
<html><body>
<article>
  <h3>OpenAI releases GPT-5 with advanced reasoning</h3>
  <time>March 28, 2026</time>
  <p>OpenAI announced the release of GPT-5, its most capable model to date...</p>
</article>
<article>
  <h3>Anthropic raises $5B in latest funding round</h3>
  <time>March 27, 2026</time>
  <p>AI safety startup Anthropic secured additional funding...</p>
</article>
</body></html>
"""

TECHCRUNCH_HTML = """
<html><body>
<article class="post-block">
  <h2 class="post-block__title"><a href="/2026/03/28/google-gemini-3/">Google launches Gemini 3.0</a></h2>
  <time class="river-byline__time">March 28, 2026</time>
  <a rel="author" href="/author/writer">AI Writer</a>
</article>
<article class="post-block">
  <h2 class="post-block__title"><a href="/2026/03/27/ai-regulation/">EU proposes new AI regulations</a></h2>
  <time class="river-byline__time">March 27, 2026</time>
  <a rel="author" href="/author/policy">Policy Reporter</a>
</article>
</body></html>
"""


def _make_source(org: str, classification: str = "secondary") -> SourceConfig:
    return SourceConfig(
        source_name=org,
        category="news",
        organization=org,
        homepage_url=f"https://{org.lower()}.com",
        base_domain=f"{org.lower()}.com",
        trust_rating=4.0,
        source_role="test",
        classification=classification,
    )


def test_reuters_extracts_articles():
    collector = ReutersCollector(_make_source("Reuters"))
    page = PageConfig(canonical_url="https://reuters.com/ai", page_type="news")
    items = collector.extract_items(REUTERS_HTML, page)
    assert len(items) == 2
    assert all(i.item_type == "news_article" for i in items)
    assert all(i.metadata["confidence_tier"] == "high_secondary" for i in items)


def test_reuters_extracts_dates():
    collector = ReutersCollector(_make_source("Reuters"))
    page = PageConfig(canonical_url="https://reuters.com/ai", page_type="news")
    items = collector.extract_items(REUTERS_HTML, page)
    assert items[0].date_text == "March 28, 2026"


def test_techcrunch_extracts_articles():
    collector = TechCrunchCollector(_make_source("TechCrunch", "discovery-only"))
    page = PageConfig(canonical_url="https://techcrunch.com/ai", page_type="news")
    items = collector.extract_items(TECHCRUNCH_HTML, page)
    assert len(items) == 2
    assert all(i.item_type == "news_article" for i in items)
    assert all(i.metadata["confidence_tier"] == "medium_discovery" for i in items)


def test_techcrunch_extracts_authors():
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    page = PageConfig(canonical_url="https://techcrunch.com/ai", page_type="news")
    items = collector.extract_items(TECHCRUNCH_HTML, page)
    assert items[0].metadata["author"] == "AI Writer"


def test_techcrunch_extracts_urls():
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    page = PageConfig(canonical_url="https://techcrunch.com/ai", page_type="news")
    items = collector.extract_items(TECHCRUNCH_HTML, page)
    assert "/google-gemini-3/" in items[0].url


def test_reuters_empty_html():
    collector = ReutersCollector(_make_source("Reuters"))
    page = PageConfig(canonical_url="https://reuters.com/ai", page_type="news")
    items = collector.extract_items("<html><body></body></html>", page)
    assert items == []
