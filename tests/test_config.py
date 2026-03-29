"""Smoke tests for configuration loading."""

from __future__ import annotations

from ai_benchmark.config.settings import PipelineSettings, load_source_catalog


def test_default_settings():
    settings = PipelineSettings()
    assert settings.database_url == "sqlite+aiosqlite:///ai_benchmark.db"
    assert settings.max_concurrency == 5
    assert settings.retry_attempts == 3
    assert settings.log_level == "INFO"


def test_load_source_catalog():
    sources = load_source_catalog()
    assert len(sources) == 22
    names = {s.source_name for s in sources}
    assert "OpenAI" in names
    assert "Anthropic" in names
    assert "Reuters AI" in names
    assert "Hugging Face Forums" in names


def test_source_trust_ratings():
    sources = load_source_catalog()
    for s in sources:
        assert 1.0 <= s.trust_rating <= 5.0


def test_source_classifications():
    sources = load_source_catalog()
    valid = {"primary", "secondary", "discovery-only"}
    for s in sources:
        assert s.classification in valid, (
            f"{s.source_name} has invalid classification: {s.classification}"
        )


def test_all_sources_have_pages():
    sources = load_source_catalog()
    for s in sources:
        assert len(s.pages) > 0, f"{s.source_name} has no pages"
