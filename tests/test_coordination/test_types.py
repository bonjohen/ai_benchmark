"""Tests for FetchTask and CoordFetchResult dataclasses."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

import pytest

from ai_benchmark.coordination.types import CoordFetchResult, FetchTask


class TestFetchTask:
    def test_construction_all_fields(self):
        task = FetchTask(
            task_id="abc123",
            organization="OpenAI",
            page_url="https://openai.com/pricing",
            page_type="pricing",
            page_id=42,
            source_id=1,
            classification="primary",
            collector_class_name="OpenAI",
            css_selectors={"main": "div.content"},
            since_date=date(2026, 1, 1),
            priority=True,
            attempt=2,
        )
        assert task.task_id == "abc123"
        assert task.organization == "OpenAI"
        assert task.page_url == "https://openai.com/pricing"
        assert task.page_type == "pricing"
        assert task.page_id == 42
        assert task.source_id == 1
        assert task.classification == "primary"
        assert task.collector_class_name == "OpenAI"
        assert task.css_selectors == {"main": "div.content"}
        assert task.since_date == date(2026, 1, 1)
        assert task.priority is True
        assert task.attempt == 2

    def test_construction_defaults(self):
        task = FetchTask(
            task_id="def456",
            organization="Anthropic",
            page_url="https://anthropic.com",
            page_type="homepage",
            page_id=None,
            source_id=2,
            classification="primary",
            collector_class_name="Anthropic",
        )
        assert task.css_selectors == {}
        assert task.since_date is None
        assert task.priority is False
        assert task.attempt == 0

    def test_frozen_immutability(self):
        task = FetchTask(
            task_id="x",
            organization="OpenAI",
            page_url="https://openai.com",
            page_type="homepage",
            page_id=1,
            source_id=1,
            classification="primary",
            collector_class_name="OpenAI",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            task.attempt = 5  # type: ignore[misc]

    def test_page_id_none(self):
        task = FetchTask(
            task_id="x",
            organization="OpenAI",
            page_url="https://openai.com",
            page_type="homepage",
            page_id=None,
            source_id=1,
            classification="primary",
            collector_class_name="OpenAI",
        )
        assert task.page_id is None


class TestCoordFetchResult:
    def test_construction_success(self):
        now = datetime(2026, 3, 30, 12, 0, 0)
        result = CoordFetchResult(
            task_id="abc123",
            organization="OpenAI",
            page_url="https://openai.com/pricing",
            page_type="pricing",
            page_id=42,
            source_id=1,
            classification="primary",
            items=["item1", "item2"],
            html_content="<html>content</html>",
            fetch_status=200,
            fetch_error=None,
            elapsed_ms=150.5,
            fetched_at=now,
            css_selectors={"main": "div.content"},
            has_custom_collect=False,
            since_date=None,
            priority=False,
            attempt=0,
        )
        assert result.task_id == "abc123"
        assert result.items == ["item1", "item2"]
        assert result.html_content == "<html>content</html>"
        assert result.fetch_status == 200
        assert result.fetch_error is None
        assert result.elapsed_ms == 150.5
        assert result.fetched_at == now
        assert result.has_custom_collect is False

    def test_construction_error_variant(self):
        result = CoordFetchResult(
            task_id="err1",
            organization="OpenAI",
            page_url="https://openai.com/pricing",
            page_type="pricing",
            page_id=42,
            source_id=1,
            classification="primary",
            items=[],
            fetch_status=500,
            fetch_error="Internal Server Error",
            attempt=1,
        )
        assert result.fetch_error == "Internal Server Error"
        assert result.items == []
        assert result.attempt == 1

    def test_has_custom_collect_true(self):
        result = CoordFetchResult(
            task_id="api1",
            organization="Ai2",
            page_url="https://api.semanticscholar.org",
            page_type="api",
            page_id=10,
            source_id=5,
            classification="secondary",
            has_custom_collect=True,
            html_content="",
        )
        assert result.has_custom_collect is True
        assert result.html_content == ""

    def test_defaults(self):
        result = CoordFetchResult(
            task_id="d",
            organization="X",
            page_url="https://x.com",
            page_type="t",
            page_id=None,
            source_id=1,
            classification="primary",
        )
        assert result.items == []
        assert result.html_content == ""
        assert result.fetch_status == 0
        assert result.fetch_error is None
        assert result.has_custom_collect is False
        assert result.since_date is None
        assert result.priority is False
        assert result.attempt == 0

    def test_mutable(self):
        """CoordFetchResult is not frozen — coordinator may annotate results."""
        result = CoordFetchResult(
            task_id="m",
            organization="X",
            page_url="https://x.com",
            page_type="t",
            page_id=None,
            source_id=1,
            classification="primary",
        )
        result.fetch_error = "timeout"
        assert result.fetch_error == "timeout"
