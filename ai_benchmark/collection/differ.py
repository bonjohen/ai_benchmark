"""HTML cleaning, text extraction, and semantic diffing engine."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

# Tags that typically contain noise, not content
NOISE_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"}

# Default CSS selectors for main content extraction (tried in order)
DEFAULT_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".content",
    "#content",
    ".post-content",
    ".entry-content",
]


def clean_html(
    html: str,
    content_selectors: list[str] | None = None,
) -> str:
    """Clean HTML by stripping noise and extracting main content text.

    Args:
        html: Raw HTML string.
        content_selectors: CSS selectors to try for main content extraction.
            Falls back to full body if none match.

    Returns:
        Cleaned, normalized text suitable for diffing.
    """
    # Detect XML content (RSS, Atom) and use appropriate parser
    stripped = html.lstrip()
    parser = "lxml-xml" if stripped.startswith(("<?xml", "<rss", "<feed")) else "lxml"
    soup = BeautifulSoup(html, parser)

    # Remove noise tags
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Try to find main content area
    selectors = content_selectors or DEFAULT_CONTENT_SELECTORS
    content_element: Tag | None = None
    for selector in selectors:
        content_element = soup.select_one(selector)
        if content_element:
            break

    if content_element is None:
        content_element = soup.body or soup

    text = content_element.get_text(separator="\n", strip=True)
    # Normalize whitespace: collapse multiple blank lines, strip trailing spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


@dataclass
class DiffResult:
    """Result of comparing two content snapshots."""

    changed: bool
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    change_ratio: float = 0.0
    diff_text: str = ""

    @property
    def is_significant(self) -> bool:
        """Whether the change exceeds the noise threshold."""
        return self.changed and self.change_ratio >= 0.01


def diff_snapshots(
    old_text: str,
    new_text: str,
    noise_threshold: float = 0.01,
) -> DiffResult:
    """Compare two cleaned text snapshots and produce a diff.

    Args:
        old_text: Previous snapshot text.
        new_text: Current snapshot text.
        noise_threshold: Minimum change_ratio to consider significant.

    Returns:
        DiffResult with change details.
    """
    if old_text == new_text:
        return DiffResult(changed=False)

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    ratio = 1.0 - matcher.ratio()

    added: list[str] = []
    removed: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added.extend(line.strip() for line in new_lines[j1:j2] if line.strip())
        elif tag == "delete":
            removed.extend(line.strip() for line in old_lines[i1:i2] if line.strip())
        elif tag == "replace":
            removed.extend(line.strip() for line in old_lines[i1:i2] if line.strip())
            added.extend(line.strip() for line in new_lines[j1:j2] if line.strip())

    diff_text = "".join(difflib.unified_diff(old_lines, new_lines, lineterm=""))

    return DiffResult(
        changed=True,
        added_lines=added,
        removed_lines=removed,
        change_ratio=ratio,
        diff_text=diff_text,
    )


def extract_structural_changes(
    old_html: str,
    new_html: str,
    item_selector: str = "li, tr, article, .entry",
) -> dict[str, list[str]]:
    """Detect structural additions/removals (new list items, table rows, articles).

    This is a higher-level diff that identifies specific structural elements
    that were added or removed, useful for changelogs, pricing tables, and newsrooms.
    """
    old_soup = BeautifulSoup(old_html, "lxml")
    new_soup = BeautifulSoup(new_html, "lxml")

    old_items = {
        el.get_text(strip=True) for el in old_soup.select(item_selector) if el.get_text(strip=True)
    }
    new_items = {
        el.get_text(strip=True) for el in new_soup.select(item_selector) if el.get_text(strip=True)
    }

    return {
        "added": sorted(new_items - old_items),
        "removed": sorted(old_items - new_items),
    }
