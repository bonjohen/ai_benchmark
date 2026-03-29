"""Tests for vendor source collectors and normalizer."""

from __future__ import annotations

import pytest

from ai_benchmark.config.settings import PageConfig, SourceConfig
from ai_benchmark.processing.normalizer import (
    classify_event_type,
    extract_date,
    extract_model_slug,
    normalize_title,
)
from ai_benchmark.sources.anthropic import AnthropicCollector
from ai_benchmark.sources.google import GoogleCollector
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
    collector = MistralCollector(_make_source("Mistral AI"))
    page = PageConfig(canonical_url="https://example.com/changelog", page_type="changelog")
    items = collector.extract_items(MISTRAL_CHANGELOG_HTML, page)
    model_items = [i for i in items if i.item_type == "model_release"]
    api_items = [i for i in items if i.item_type == "api_update"]
    assert len(model_items) >= 1
    assert len(api_items) >= 1


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
