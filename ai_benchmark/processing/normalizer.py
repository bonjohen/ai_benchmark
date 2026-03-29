"""Event field normalization: title, model slugs, versions, dates, event types."""

from __future__ import annotations

import re
from datetime import datetime

# Known model family patterns — capture model name + version + variant
# Uses word boundaries and captures up to 5 additional name parts, trimmed by stop words
MODEL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(gpt-[\w.-]+)", re.IGNORECASE),
    re.compile(r"\b(o[1-9][\w.-]*)", re.IGNORECASE),
    re.compile(r"\b(claude[\s-][\d]+(?:\.[\d]+)?(?:[\s-][A-Z][\w]*){0,3})", re.IGNORECASE),
    re.compile(r"\b(gemini[\s-][\d]+(?:\.[\d]+)?(?:[\s-][A-Z][\w]*){0,3})", re.IGNORECASE),
    re.compile(r"\b(grok[\s-][\d]+(?:\.[\d]+)?(?:[\s-][A-Z][\w]*){0,3})", re.IGNORECASE),
    re.compile(r"\b(mistral[\s-][A-Z][\w]*(?:[\s-][\w]+){0,2})", re.IGNORECASE),
    re.compile(r"\b(codestral[\s-][\w]+)", re.IGNORECASE),
    re.compile(r"\b(pixtral[\s-][\w]+)", re.IGNORECASE),
    re.compile(r"\b(command[\s-][A-Z][\w]*(?:[\s-][\w]+){0,2})", re.IGNORECASE),
    re.compile(r"\b(llama[\s-][\d]+(?:\.[\d]+)?(?:[\s-][A-Z][\w]*){0,3})", re.IGNORECASE),
]

# Date formats commonly found in changelogs and newsrooms
DATE_FORMATS = [
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
]

# Event type classification keywords
EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "model_release": [
        "released",
        "launch",
        "introducing",
        "announcing",
        "now available",
        "new model",
    ],
    "pricing_change": ["pricing", "price", "cost", "rate", "per token", "per million"],
    "api_update": ["api", "endpoint", "sdk", "changelog", "feature"],
    "deprecation": ["deprecated", "deprecation", "sunset", "retiring", "end of life", "removed"],
    "system_card": ["system card", "model card", "safety", "evaluation"],
    "announcement": ["announcement", "partnership", "acquisition", "update", "blog"],
}


def normalize_title(raw_title: str) -> str:
    """Normalize a title for dedup: lowercase, strip whitespace, collapse spaces."""
    title = raw_title.strip().lower()
    title = re.sub(r"\s+", " ", title)
    return title


# Words that signal end of a model name
_STOP_WORDS = {
    "is",
    "was",
    "are",
    "were",
    "with",
    "and",
    "the",
    "a",
    "an",
    "for",
    "in",
    "on",
    "at",
    "to",
    "from",
    "by",
    "has",
    "have",
    "had",
    "now",
    "will",
    "can",
    "may",
    "should",
    "would",
    "could",
    "been",
    "being",
}


def extract_model_slug(text: str) -> str | None:
    """Extract the first recognized model slug from text."""
    for pattern in MODEL_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            # Trim trailing stop words
            words = raw.split()
            while len(words) > 1 and words[-1].lower() in _STOP_WORDS:
                words.pop()
            slug = " ".join(words)
            # Normalize whitespace to hyphen
            slug = re.sub(r"\s+", "-", slug).lower()
            return slug
    return None


def extract_version(text: str) -> str | None:
    """Extract a version string like v1.2.3 or 2026-03-28."""
    # Semver-like
    match = re.search(r"\bv?(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)\b", text)
    if match:
        return match.group(1)
    # Date-based version
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)
    return None


def extract_date(text: str) -> str | None:
    """Extract and normalize the first date found in text to YYYY-MM-DD."""
    # Try ISO format first
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)

    for fmt in DATE_FORMATS:
        # Find date-like substrings and try parsing
        try:
            # Month name formats
            match = re.search(
                r"\b(\w+ \d{1,2},? \d{4}|\d{1,2} \w+ \d{4}"
                r"|\d{1,2}/\d{1,2}/\d{4}|\d{4}/\d{2}/\d{2})\b",
                text,
            )
            if match:
                dt = datetime.strptime(match.group(1), fmt)
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# Source classification → confidence tier mapping (5 tiers)
CONFIDENCE_TIERS: dict[str, str] = {
    "primary": "official_self_report",
    "secondary": "high_secondary",
    "benchmark_owner": "benchmark_owner_report",
    "news_medium": "medium_discovery",
    "discovery-only": "low_discovery",
}

# Source-specific tier overrides: (organization, source_type) -> confidence tier
SOURCE_TIER_OVERRIDES: dict[tuple[str, str], str] = {
    ("Reuters", "news_index"): "high_secondary",
    ("TechCrunch", "news_index"): "medium_discovery",
    ("SWE-bench", "leaderboard"): "benchmark_owner_report",
    ("GAIA", "leaderboard"): "benchmark_owner_report",
    ("LiveBench", "leaderboard"): "benchmark_owner_report",
    ("LMArena", "leaderboard"): "benchmark_owner_report",
    ("HLE", "leaderboard"): "benchmark_owner_report",
    ("Terminal-Bench", "leaderboard"): "benchmark_owner_report",
    ("Artificial Analysis", "leaderboard"): "benchmark_owner_report",
}


def confidence_tier_for_classification(
    classification: str,
    organization: str | None = None,
    source_type: str | None = None,
) -> str:
    """Map a source classification to the appropriate confidence tier.

    Checks SOURCE_TIER_OVERRIDES first, then falls back to CONFIDENCE_TIERS.
    """
    if organization and source_type:
        override = SOURCE_TIER_OVERRIDES.get((organization, source_type))
        if override:
            return override
    return CONFIDENCE_TIERS.get(classification, "low_discovery")


def classify_event_type(title: str, body: str = "") -> str:
    """Classify an event into one of the defined types based on keywords."""
    combined = f"{title} {body}".lower()
    scores: dict[str, int] = {}
    for event_type, keywords in EVENT_TYPE_KEYWORDS.items():
        scores[event_type] = sum(1 for kw in keywords if kw in combined)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return "announcement"
