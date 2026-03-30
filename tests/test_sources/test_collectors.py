"""Tests for vendor source collectors and normalizer."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.processing.normalizer import (
    classify_event_type,
    extract_date,
    extract_model_slug,
    normalize_title,
    validate_model_slug,
)
from ai_benchmark.sources.anthropic import AnthropicCollector
from ai_benchmark.sources.base import extract_nextjs_rsc_payloads
from ai_benchmark.sources.benchmarks.lmarena import LMArenaCollector
from ai_benchmark.sources.google import GoogleCollector
from ai_benchmark.sources.meta import MetaCollector
from ai_benchmark.sources.mistral import MistralCollector
from ai_benchmark.sources.openai import OpenAICollector
from ai_benchmark.sources.registry import get_collector, list_registered_organizations

# ─── Normalizer tests ───


def test_normalize_title():
    assert normalize_title("  GPT-5  Released  ") == "gpt-5 released"
    assert normalize_title("HELLO\t WORLD") == "hello world"


def test_extract_model_slug_gpt():
    assert extract_model_slug("Released GPT-4.5-turbo with 256k context") == "gpt-4.5-turbo"


def test_extract_model_slug_claude():
    assert extract_model_slug("Announcing Claude 3.5 Sonnet") == "claude-3.5-sonnet"


def test_extract_model_slug_gemini():
    assert extract_model_slug("Gemini 2.0 Flash is now available") == "gemini-2.0-flash"


def test_extract_model_slug_llama():
    assert extract_model_slug("Meta releases Llama 4 Scout") == "llama-4-scout"


def test_extract_model_slug_none():
    assert extract_model_slug("General announcement about AI safety") is None


# ─── validate_model_slug tests ───


def test_validate_model_slug_accepts_real_models():
    assert validate_model_slug("gpt-4o") == "gpt-4o"
    assert validate_model_slug("claude-3.5-sonnet") == "claude-3.5-sonnet"
    assert validate_model_slug("gemini-2.0-flash") == "gemini-2.0-flash"
    assert validate_model_slug("llama-4-scout") == "llama-4-scout"
    assert validate_model_slug("mistral-large") == "mistral-large"


def test_validate_model_slug_rejects_programming_languages():
    assert validate_model_slug("Rust") is None
    assert validate_model_slug("Go") is None
    assert validate_model_slug("Java") is None
    assert validate_model_slug("Python") is None
    assert validate_model_slug("C/C++") is None
    assert validate_model_slug("JavaScript/TypeScript") is None
    assert validate_model_slug("ruby") is None
    assert validate_model_slug("PHP") is None


def test_validate_model_slug_rejects_repo_paths():
    assert validate_model_slug("redis/redis") is None
    assert validate_model_slug("tokio-rs/tokio") is None
    assert validate_model_slug("babel/babel") is None
    assert validate_model_slug("vuejs/core") is None


def test_validate_model_slug_rejects_aggregate_labels():
    assert validate_model_slug("Total") is None
    assert validate_model_slug("average") is None
    assert validate_model_slug("baseline") is None
    assert validate_model_slug("human") is None


def test_validate_model_slug_rejects_year_labels():
    assert validate_model_slug("2022") is None
    assert validate_model_slug("≤2021") is None
    assert validate_model_slug("2025") is None


def test_validate_model_slug_rejects_feature_terms():
    assert validate_model_slug("free") is None
    assert validate_model_slug("Pro") is None
    assert validate_model_slug("enterprise") is None


def test_validate_model_slug_rejects_numeric_ids():
    assert validate_model_slug("19") is None
    assert validate_model_slug("333") is None
    assert validate_model_slug("1528") is None


def test_validate_model_slug_rejects_generic_words():
    assert validate_model_slug("Model") is None
    assert validate_model_slug("test") is None


def test_validate_model_slug_rejects_empty_or_short():
    assert validate_model_slug("") is None
    assert validate_model_slug("a") is None
    assert validate_model_slug("x" * 101) is None


def test_extract_date_iso():
    assert extract_date("Updated on 2026-03-28") == "2026-03-28"


def test_extract_date_long_format():
    assert extract_date("March 15, 2026 — Released gpt-5") == "2026-03-15"


def test_classify_model_release():
    assert classify_event_type("Released GPT-5 with 1M context") == "model_release"


def test_classify_pricing():
    assert classify_event_type("Updated pricing for API tokens") == "pricing_change"


def test_classify_deprecation():
    assert classify_event_type("Deprecated gpt-4-32k") == "deprecation"


def test_classify_api_update():
    assert classify_event_type("New API endpoint for batch processing") == "api_update"


# ─── RSC payload extraction tests ───


def test_extract_nextjs_rsc_payloads_basic():
    html = """
    <html><body>
    <script>self.__next_f.push([1,"hello world"])</script>
    <script>self.__next_f.push([1,"second payload"])</script>
    </body></html>
    """
    payloads = extract_nextjs_rsc_payloads(html)
    assert len(payloads) == 2
    assert payloads[0] == "hello world"
    assert payloads[1] == "second payload"


def test_extract_nextjs_rsc_payloads_empty():
    html = "<html><body><h1>No RSC here</h1></body></html>"
    payloads = extract_nextjs_rsc_payloads(html)
    assert payloads == []


def test_extract_nextjs_rsc_payloads_escaped():
    html = r"""
    <html><body>
    <script>self.__next_f.push([1,"escaped \"quotes\" and \\backslash"])</script>
    <script>self.__next_f.push([1,"unicode \u0041\u0042\u0043"])</script>
    </body></html>
    """
    payloads = extract_nextjs_rsc_payloads(html)
    assert len(payloads) == 2
    assert 'escaped "quotes" and \\backslash' in payloads[0]
    assert "ABC" in payloads[1]


# ─── Collector extraction tests ───

CHANGELOG_HTML = """
<html><body><main>
<h1>API Changelog</h1>
<ul>
<li><strong>2026-03-28</strong> — Released gpt-5 with 1M context window.</li>
<li><strong>2026-03-15</strong> — Released gpt-4.5-turbo with 256k context.</li>
</ul>
</main></body></html>
"""

PRICING_HTML = """
<html><body><main>
<table>
<tr><th>Model</th><th>Input</th><th>Output</th></tr>
<tr><td>gpt-5</td><td>$5.00</td><td>$15.00</td></tr>
<tr><td>gpt-4o</td><td>$2.50</td><td>$10.00</td></tr>
</table>
</main></body></html>
"""

MISTRAL_CHANGELOG_HTML = """
<html><body><main>
<section>
<h2>February 2026</h2>
<li>MODEL RELEASED: Mistral Large 3 — the latest frontier model</li>
<li>API UPDATED: Added OCR endpoint for document processing</li>
</section>
</main></body></html>
"""


def _make_source(org: str) -> SourceConfig:
    return SourceConfig(
        source_name=org,
        category="official company source",
        organization=org,
        homepage_url=f"https://{org.lower().replace(' ', '')}.com",
        base_domain=f"{org.lower().replace(' ', '')}.com",
        trust_rating=5.0,
        source_role="test",
        classification="primary",
    )


def test_openai_changelog_extraction():
    collector = OpenAICollector(_make_source("OpenAI"))
    page = PageConfig(canonical_url="https://example.com/changelog", page_type="api changelog")
    items = collector.extract_items(CHANGELOG_HTML, page)
    assert len(items) >= 2
    assert any("gpt-5" in item.title.lower() for item in items)


def test_openai_pricing_extraction():
    collector = OpenAICollector(_make_source("OpenAI"))
    page = PageConfig(canonical_url="https://example.com/pricing", page_type="pricing")
    items = collector.extract_items(PRICING_HTML, page)
    assert len(items) >= 2
    assert any(item.model_hint == "gpt-5" for item in items)


def test_anthropic_newsroom_extraction():
    html = """
    <html><body><main>
    <a href="/news/claude-4"><h3>Introducing Claude 4</h3></a>
    <a href="/news/safety"><h3>Safety Update</h3></a>
    </main></body></html>
    """
    collector = AnthropicCollector(_make_source("Anthropic"))
    page = PageConfig(canonical_url="https://example.com/news", page_type="newsroom")
    items = collector.extract_items(html, page)
    assert len(items) >= 2
    assert any("Claude" in item.title for item in items)


def test_google_changelog_extraction():
    html = """
    <html><body><main>
    <h2>March 2026</h2>
    <h3>Released Gemini 2.5 Pro with enhanced reasoning</h3>
    <h3>Updated rate limits for batch API</h3>
    </main></body></html>
    """
    collector = GoogleCollector(_make_source("Google"))
    page = PageConfig(canonical_url="https://example.com/changelog", page_type="api changelog")
    items = collector.extract_items(html, page)
    assert len(items) >= 2


def test_mistral_changelog_labels():
    """Fallback extraction works with traditional DOM HTML."""
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(canonical_url="https://example.com/changelog", page_type="changelog")
    items = collector.extract_items(MISTRAL_CHANGELOG_HTML, page)
    model_items = [i for i in items if i.item_type == "model_release"]
    api_items = [i for i in items if i.item_type == "api_update"]
    assert len(model_items) >= 1
    assert len(api_items) >= 1


# ─── Mistral RSC fixture tests ───

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_mistral_changelog_extraction():
    """RSC payload extraction returns items from real changelog HTML."""
    fixture = FIXTURES_DIR / "mistral_changelog.html"
    if not fixture.exists():
        pytest.skip("Mistral changelog fixture not available")
    html = fixture.read_text(encoding="utf-8")
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://docs.mistral.ai/getting-started/changelog",
        page_type="changelog",
    )
    items = collector.extract_items(html, page)
    assert len(items) >= 20
    model_items = [i for i in items if i.item_type == "model_release"]
    api_items = [i for i in items if i.item_type == "api_update"]
    assert len(model_items) >= 10
    assert len(api_items) >= 5


def test_mistral_changelog_date_extraction():
    """Changelog items from RSC payloads include date_text."""
    fixture = FIXTURES_DIR / "mistral_changelog.html"
    if not fixture.exists():
        pytest.skip("Mistral changelog fixture not available")
    html = fixture.read_text(encoding="utf-8")
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://docs.mistral.ai/getting-started/changelog",
        page_type="changelog",
    )
    items = collector.extract_items(html, page)
    dated = [i for i in items if i.date_text]
    assert len(dated) >= 20
    # Dates should be YYYY-MM-DD format
    for item in dated:
        assert len(item.date_text) == 10  # noqa: PLR2004
        assert item.date_text[4] == "-"


def test_mistral_fallback_on_empty_rsc():
    """Extraction methods fall back gracefully when no RSC payloads found."""
    plain_html = "<html><body><li>MODEL RELEASED: Some model</li></body></html>"
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://docs.mistral.ai/getting-started/changelog",
        page_type="changelog",
    )
    items = collector.extract_items(plain_html, page)
    # Falls back to DOM-based extraction
    assert len(items) >= 1
    assert items[0].item_type == "model_release"


def test_mistral_news_extraction():
    """RSC payload extraction returns news posts from real news HTML."""
    fixture = FIXTURES_DIR / "mistral_news.html"
    if not fixture.exists():
        pytest.skip("Mistral news fixture not available")
    html = fixture.read_text(encoding="utf-8")
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://mistral.ai/news/",
        page_type="news",
    )
    items = collector.extract_items(html, page)
    assert len(items) >= 10
    assert all(item.item_type == "news_post" for item in items)
    assert any("Mistral" in item.title for item in items)


def test_mistral_news_url_resolution():
    """News post URLs are resolved to absolute https://mistral.ai/news/... paths."""
    fixture = FIXTURES_DIR / "mistral_news.html"
    if not fixture.exists():
        pytest.skip("Mistral news fixture not available")
    html = fixture.read_text(encoding="utf-8")
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://mistral.ai/news/",
        page_type="news",
    )
    items = collector.extract_items(html, page)
    for item in items:
        assert item.url.startswith("https://mistral.ai/news/"), f"Bad URL: {item.url}"


# ─── LMArena collector tests ───

LMARENA_SUBPAGE_HTML = """
<html><body><table>
<tr><th>Rank</th><th>Spread</th><th>Model</th><th>Score</th>
    <th>Votes</th><th>Price</th><th>Context</th></tr>
<tr>
  <td>1</td><td>14</td>
  <td><div><div><svg><title>Anthropic</title></svg></div>
    <div><div><a href="/m/claude-opus-4-6-thinking">
      <span class="max-w-full truncate">claude-opus-4-6-thinking</span>
    </a></div><span>Anthropic · Proprietary</span></div></div></td>
  <td><span class="text-sm">1504</span><span>±6</span></td>
  <td>12,730</td><td>$5/$25</td><td>1M</td>
</tr>
<tr>
  <td>2</td><td>12</td>
  <td><div><div><svg><title>Google</title></svg></div>
    <div><div><a href="/m/gemini-3-pro">
      <span class="max-w-full truncate">gemini-3-pro</span>
    </a></div><span>Google · Proprietary</span></div></div></td>
  <td><span class="text-sm">1486</span><span>±4</span></td>
  <td>45,200</td><td>$1.25/$10</td><td>1M</td>
</tr>
</table></body></html>
"""

LMARENA_MAINPAGE_HTML = """
<html><body>
<table>
<tr><th>Rank</th><th>Model</th><th>Score</th><th>Votes</th></tr>
<tr>
  <td>1</td>
  <td><div><div><a href="/m/claude-opus-4-6">
    <span class="max-w-full truncate">claude-opus-4-6</span>
  </a></div><span>Anthropic · Proprietary</span></div></td>
  <td><span>1500</span><span>±6</span></td>
  <td>10,000</td>
</tr>
<tr>
  <td>2</td>
  <td><div><div><a href="/m/gpt-5.4">
    <span class="max-w-full truncate">gpt-5.4</span>
  </a></div><span>OpenAI · Proprietary</span></div></td>
  <td><span>1450</span><span>±5</span></td>
  <td>8,500</td>
</tr>
</table>
</body></html>
"""


def test_lmarena_subpage_extraction():
    """7-column sub-page: model at col 2, score at col 3."""
    collector = LMArenaCollector(_make_source("LMArena"))
    page = PageConfig(
        canonical_url="https://arena.ai/leaderboard/text",
        page_type="leaderboard",
    )
    entries = collector.extract_leaderboard(LMARENA_SUBPAGE_HTML, page)
    assert len(entries) == 2

    assert entries[0].model == "claude-opus-4-6-thinking"
    assert entries[0].score == "1504"
    assert entries[0].rank == 1
    assert entries[0].variant == "arena_elo_text"
    assert entries[0].metadata.get("organization") == "Anthropic"

    assert entries[1].model == "gemini-3-pro"
    assert entries[1].score == "1486"
    assert entries[1].rank == 2


def test_lmarena_mainpage_extraction():
    """4-column main page: model at col 1, score at col 2."""
    collector = LMArenaCollector(_make_source("LMArena"))
    page = PageConfig(
        canonical_url="https://arena.ai/leaderboard/",
        page_type="leaderboard",
    )
    entries = collector.extract_leaderboard(LMARENA_MAINPAGE_HTML, page)
    assert len(entries) == 2

    assert entries[0].model == "claude-opus-4-6"
    assert entries[0].score == "1500"
    assert entries[0].rank == 1
    assert entries[0].variant == "arena_elo"

    assert entries[1].model == "gpt-5.4"
    assert entries[1].score == "1450"
    assert entries[1].rank == 2


def test_lmarena_variant_derivation():
    """Different page URLs produce distinct variants."""
    collector = LMArenaCollector(_make_source("LMArena"))
    for suffix, expected in [
        ("text", "arena_elo_text"),
        ("code", "arena_elo_code"),
        ("vision", "arena_elo_vision"),
    ]:
        page = PageConfig(
            canonical_url=f"https://arena.ai/leaderboard/{suffix}",
            page_type="leaderboard",
        )
        entries = collector.extract_leaderboard(LMARENA_SUBPAGE_HTML, page)
        assert entries[0].variant == expected


def test_lmarena_items_have_correct_titles():
    """extract_items() produces clean titles with model name and Elo score."""
    collector = LMArenaCollector(_make_source("LMArena"))
    page = PageConfig(
        canonical_url="https://arena.ai/leaderboard/text",
        page_type="leaderboard",
    )
    items = collector.extract_items(LMARENA_SUBPAGE_HTML, page)
    assert len(items) == 2
    assert items[0].title == "LMArena: claude-opus-4-6-thinking = 1504"
    assert items[0].model_hint == "claude-opus-4-6-thinking"


# ─── Model catalog tests ───

MISTRAL_MODEL_DOCS_HTML = """
<html><body><main>
<h1>Models</h1>
<table>
<tr><th>Model</th><th>Description</th><th>Context</th></tr>
<tr><td>Mistral Large</td><td>Flagship model for complex tasks</td><td>128k</td></tr>
<tr><td>Mistral Small</td><td>Efficient model for simple tasks</td><td>32k</td></tr>
</table>
<section>
<h3>Codestral</h3>
<p>Specialized code generation model with fill-in-the-middle support</p>
</section>
</main></body></html>
"""


def test_mistral_model_docs_extraction():
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(
        canonical_url="https://docs.mistral.ai/models",
        page_type="model catalog",
    )
    items = collector.extract_items(MISTRAL_MODEL_DOCS_HTML, page)
    assert len(items) >= 2
    assert all(item.item_type == "model_entry" for item in items)
    assert any("mistral" in item.title.lower() for item in items)


def test_meta_model_docs_extraction():
    collector = MetaCollector(_make_source("Meta"), github_token=None)
    page = PageConfig(
        canonical_url="https://llama.meta.com/",
        page_type="model catalog",
    )
    html = """
    <html><body>
    <section><h3>Llama 4 Scout</h3><p>Open-weight model for general use</p></section>
    <section><h3>Llama 4 Maverick</h3><p>Large open-weight model</p></section>
    </body></html>
    """
    items = collector.extract_items(html, page)
    assert len(items) >= 2
    assert all(item.item_type == "model_entry" for item in items)
    assert any("llama" in item.title.lower() for item in items)


# ─── Registry tests ───


def test_registered_organizations():
    orgs = list_registered_organizations()
    assert "OpenAI" in orgs
    assert "Anthropic" in orgs
    assert "Google" in orgs
    assert "Meta" in orgs


def test_get_collector_openai():
    source = _make_source("OpenAI")
    collector = get_collector(source)
    assert isinstance(collector, OpenAICollector)


def test_get_collector_unknown_raises():
    source = _make_source("UnknownOrg")
    with pytest.raises(ValueError, match="No collector registered"):
        get_collector(source)
