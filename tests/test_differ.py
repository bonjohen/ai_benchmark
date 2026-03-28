"""Tests for HTML cleaning and diffing."""

from __future__ import annotations

from pathlib import Path

from ai_benchmark.collection.differ import (
    clean_html,
    diff_snapshots,
    extract_structural_changes,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_html_strips_noise():
    html = """
    <html><body>
    <script>alert('x')</script>
    <style>.foo{}</style>
    <nav>Nav stuff</nav>
    <main><p>Real content here.</p></main>
    <footer>Footer stuff</footer>
    </body></html>
    """
    text = clean_html(html)
    assert "Real content here." in text
    assert "alert" not in text
    assert "Nav stuff" not in text
    assert "Footer stuff" not in text


def test_clean_html_uses_custom_selectors():
    html = '<html><body><div class="custom"><p>Found it</p></div><p>Noise</p></body></html>'
    text = clean_html(html, content_selectors=[".custom"])
    assert "Found it" in text
    assert "Noise" not in text


def test_diff_identical():
    result = diff_snapshots("same text", "same text")
    assert not result.changed
    assert result.change_ratio == 0.0


def test_diff_detects_additions():
    old = "line 1\nline 2\n"
    new = "line 1\nline 2\nline 3 new\n"
    result = diff_snapshots(old, new)
    assert result.changed
    assert any("line 3 new" in line for line in result.added_lines)
    assert len(result.removed_lines) == 0


def test_diff_detects_removals():
    old = "line 1\nline 2\nline 3"
    new = "line 1\nline 3"
    result = diff_snapshots(old, new)
    assert result.changed
    assert any("line 2" in line for line in result.removed_lines)


def test_diff_change_ratio():
    old = "a\nb\nc\nd\ne"
    new = "a\nb\nc\nd\ne\nf"
    result = diff_snapshots(old, new)
    assert result.changed
    assert 0 < result.change_ratio < 0.5


def test_diff_changelog_fixtures():
    v1 = (FIXTURES / "changelog_v1.html").read_text()
    v2 = (FIXTURES / "changelog_v2.html").read_text()
    text1 = clean_html(v1)
    text2 = clean_html(v2)
    result = diff_snapshots(text1, text2)
    assert result.changed
    assert result.is_significant
    assert any("gpt-5" in line for line in result.added_lines)


def test_structural_changes():
    v1 = (FIXTURES / "changelog_v1.html").read_text()
    v2 = (FIXTURES / "changelog_v2.html").read_text()
    changes = extract_structural_changes(v1, v2, item_selector="li")
    assert len(changes["added"]) == 1
    assert "gpt-5" in changes["added"][0]
    assert len(changes["removed"]) == 0
