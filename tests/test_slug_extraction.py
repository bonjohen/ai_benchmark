"""Tests for enhanced model slug extraction: dictionary, whitespace repair, regex fallback."""

from __future__ import annotations

from ai_benchmark.processing.normalizer import (
    _match_known_model,
    _repair_whitespace,
    extract_model_slug,
)

# --- Whitespace repair ---


def test_repair_camel_boundary():
    assert _repair_whitespace("launchedClaude") == "launched Claude"
    assert _repair_whitespace("FeatureClaude") == "Feature Claude"


def test_repair_preserves_normal():
    assert _repair_whitespace("Claude Opus 4.6") == "Claude Opus 4.6"
    assert _repair_whitespace("gpt-5") == "gpt-5"


def test_repair_multiple_boundaries():
    assert _repair_whitespace("launchedClaudeOpus") == "launched Claude Opus"


# --- Dictionary matching ---


def test_known_claude_opus():
    assert _match_known_model("We've launched Claude Opus 4.6") == "claude-opus-4.6"


def test_known_claude_sonnet():
    assert _match_known_model("Claude Sonnet 4.5 is available") == "claude-sonnet-4.5"


def test_known_gpt():
    assert _match_known_model("OpenAI released GPT-5") == "gpt-5"


def test_known_gemini():
    assert _match_known_model("Gemini 3 Pro beats the competition") == "gemini-3-pro"


def test_known_llama():
    assert _match_known_model("Meta releases Llama 3.3") == "llama-3.3"


def test_known_longest_match():
    # "claude opus 4.6" (16 chars) should win over "claude opus 4" (13 chars)
    assert _match_known_model("Claude Opus 4.6 released") == "claude-opus-4.6"


def test_known_no_match():
    assert _match_known_model("This is about AI safety research") is None


def test_known_html_concatenated():
    # CamelCase from HTML stripping: "launchedClaude Opus 4.6"
    assert _match_known_model("launchedClaude Opus 4.6") == "claude-opus-4.6"


def test_known_feature_concatenated():
    # "FeatureClaude Opus 4.6Claude Sonnet 4.6Claude Haiku 4.5"
    result = _match_known_model("FeatureClaude Opus 4.6Claude Sonnet 4.6")
    # Should match the first/longest one found
    assert result in ("claude-opus-4.6", "claude-sonnet-4.6")


# --- Full extract_model_slug ---


def test_extract_known_model():
    assert extract_model_slug("We've launched Claude Opus 4.6, our best model") == "claude-opus-4.6"


def test_extract_html_concatenated():
    assert extract_model_slug("launchedClaude Sonnet 4.6, our latest") == "claude-sonnet-4.6"


def test_extract_regex_fallback():
    # Model not in dictionary but matches regex pattern
    assert extract_model_slug("Introducing Codestral Mamba") == "codestral-mamba"


def test_extract_gpt_variant():
    assert extract_model_slug("Testing GPT-4o performance") == "gpt-4o"


def test_extract_no_model():
    assert extract_model_slug("This is about AI safety research") is None


def test_extract_pricing_page():
    # Pricing table text that previously returned None
    result = extract_model_slug("Claude Opus 4.6 $5 per million input tokens")
    assert result == "claude-opus-4.6"


def test_extract_multi_model_picks_one():
    # Both are same length; either match is acceptable
    result = extract_model_slug("Claude Opus 4.6 and Claude Sonnet 4.6")
    assert result in ("claude-opus-4.6", "claude-sonnet-4.6")


def test_extract_deepseek():
    assert extract_model_slug("DeepSeek V3 dominates benchmarks") == "deepseek-v3"


def test_extract_deepseek_hyphenated():
    assert extract_model_slug("deepseek-v3 on the leaderboard") == "deepseek-v3"


def test_extract_qwen():
    assert extract_model_slug("Qwen 2.5 released by Alibaba") == "qwen-2.5"
