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
  <h2 class="post-block__title"><a href="/2026/03/28/google-gemini-3/"
    >Google launches Gemini 3.0</a></h2>
  <time class="river-byline__time">March 28, 2026</time>
  <a rel="author" href="/author/writer">AI Writer</a>
</article>
<article class="post-block">
  <h2 class="post-block__title"><a href="/2026/03/27/ai-regulation/"
    >EU proposes new AI regulations</a></h2>
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


# ─── TechCrunch RSS Parsing ───

TECHCRUNCH_RSS_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <item>
    <title>OpenAI launches GPT-5 API</title>
    <link>https://techcrunch.com/2026/03/28/openai-gpt5/</link>
    <pubDate>Thu, 28 Mar 2026 12:00:00 +0000</pubDate>
    <description>OpenAI released GPT-5 today.</description>
  </item>
  <item>
    <title>Anthropic raises new round</title>
    <link>https://techcrunch.com/2026/03/27/anthropic-funding/</link>
    <pubDate>Wed, 27 Mar 2026 10:00:00 +0000</pubDate>
    <description>Anthropic secured funding.</description>
  </item>
</channel>
</rss>"""

TECHCRUNCH_RSS_WITH_BOM = "\ufeff" + TECHCRUNCH_RSS_VALID

TECHCRUNCH_RSS_MALFORMED = """<rss>
<channel>
<item><title><![CDATA[GPT-5 released]]></title>
<link>https://tc.com/gpt5</link>
<pubDate>Thu, 28 Mar 2026</pubDate></item>
<item><title>Another article</title>
<link>https://tc.com/other</link></item>
</channel></rss>"""


def test_techcrunch_rss_valid():
    """Standard RSS feed parses correctly."""
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    page = PageConfig(canonical_url="https://tc.com/feed/", page_type="rss feed")
    items = collector.extract_items(TECHCRUNCH_RSS_VALID, page)
    assert len(items) == 2
    assert items[0].title == "OpenAI launches GPT-5 API"
    assert items[0].url == "https://techcrunch.com/2026/03/28/openai-gpt5/"


def test_techcrunch_rss_with_bom():
    """RSS feed with UTF-8 BOM still parses."""
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    page = PageConfig(canonical_url="https://tc.com/feed/", page_type="rss feed")
    items = collector.extract_items(TECHCRUNCH_RSS_WITH_BOM, page)
    assert len(items) == 2


def test_techcrunch_regex_fallback():
    """Regex fallback extracts items from malformed XML."""
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    # Test the regex method directly
    items = collector._regex_extract_rss(TECHCRUNCH_RSS_MALFORMED)
    assert len(items) == 2
    assert items[0].title == "GPT-5 released"
    assert items[1].title == "Another article"


def test_techcrunch_rss_empty():
    """Empty RSS returns empty list."""
    collector = TechCrunchCollector(_make_source("TechCrunch"))
    page = PageConfig(canonical_url="https://tc.com/feed/", page_type="rss feed")
    items = collector.extract_items("<html></html>", page)
    assert items == []
