"""Event field normalization: title, model slugs, versions, dates, event types."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Known model variant tokens (used in trailing captures after version numbers)
_VARIANT_TOKENS = (
    r"(?:Pro|Ultra|Flash|Lite|Scout|Maverick|Sonnet|Opus|Haiku|"
    r"Thinking|Turbo|Mini|Nano|Large|Medium|Small|Preview|Instruct|"
    r"Chat|Latest|Nightly|Exp|Plus|Max|Base|Tiny|Giant|High)"
)

# Known model family patterns — capture model name + version + known variant tokens
MODEL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(gpt-[\w.-]+)", re.IGNORECASE),
    re.compile(r"\b(o[1-9][\w.-]*)", re.IGNORECASE),
    # Claude: "Claude Opus 4.6", "Claude 3.5 Sonnet", "Claude Sonnet 4"
    re.compile(
        r"\b(claude(?:[\s-](?:opus|sonnet|haiku))?"
        r"[\s-][\d]+(?:\.[\d]+)?"
        rf"(?:[\s-]{_VARIANT_TOKENS}){{0,2}})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(gemini[\s-][\d]+(?:\.[\d]+)?"
        rf"(?:[\s-]{_VARIANT_TOKENS}){{0,2}})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(grok[\s-][\d]+(?:\.[\d]+)?"
        rf"(?:[\s-]{_VARIANT_TOKENS}){{0,2}})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(mistral[\s-]{_VARIANT_TOKENS}(?:[\s-][\w]+){{0,1}})",
        re.IGNORECASE,
    ),
    re.compile(r"\b(codestral[\s-][\w]+)", re.IGNORECASE),
    re.compile(r"\b(pixtral[\s-][\w]+)", re.IGNORECASE),
    # Command R, Command R+, Command A — single letter + optional plus
    re.compile(r"\b(command[\s-][A-Za-z]\+?(?:[\s-][\w]+){0,1})", re.IGNORECASE),
    re.compile(
        r"\b(llama[\s-][\d]+(?:\.[\d]+)?"
        rf"(?:[\s-]{_VARIANT_TOKENS}){{0,2}})",
        re.IGNORECASE,
    ),
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
    # Articles, prepositions, conjunctions
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
    # Headline verbs/adjectives that appear after model names in titles
    "becomes",
    "beats",
    "hits",
    "wins",
    "leads",
    "tops",
    "reaches",
    "achieves",
    "scores",
    "gets",
    "sets",
    "takes",
    "shows",
    "released",
    "launches",
    "announced",
    "available",
    "delivers",
    # Common headline nouns that aren't model variants
    "top",
    "new",
    "best",
    "first",
    "model",
    "benchmark",
    "leaderboard",
    "performance",
    "update",
    "release",
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


# Known non-model strings that should never be stored as model_slug.
# Normalized to lowercase for case-insensitive comparison.
_NON_MODEL_BLOCKLIST: set[str] = {
    # Programming languages
    "c",
    "c++",
    "c/c++",
    "dart",
    "elixir",
    "erlang",
    "go",
    "haskell",
    "java",
    "javascript",
    "javascript/typescript",
    "kotlin",
    "lua",
    "nim",
    "objective-c",
    "perl",
    "php",
    "python",
    "r",
    "ruby",
    "rust",
    "scala",
    "swift",
    "typescript",
    "zig",
    # Aggregate / metadata labels
    "total",
    "average",
    "median",
    "mean",
    "overall",
    "aggregate",
    "combined",
    "all",
    "baseline",
    "human",
    "random",
    "n/a",
    "none",
    "unknown",
    # Product/feature terms (not model names)
    "free",
    "pro",
    "enterprise",
    "preview",
    "beta",
    "alpha",
    "standard",
    "premium",
    "basic",
}

# Bare year pattern: "2019" through "2030" and partial labels like "≤2021"
_BARE_YEAR_RE = re.compile(r"^[≤≥<>]?\d{4}$")

# Words that can never be part of a model slug (pricing, features, headlines)
_SLUG_POISON_WORDS = {
    # Pricing/billing terms
    "price",
    "pricing",
    "tier",
    "tuning",
    "input",
    "output",
    # Feature/product terms
    "grounding",
    "caching",
    "execution",
    "generation",
    "endpoint",
    "agents",
    "api",
    # Concatenation artifacts
    "deprecated",
    "isdeprecatedand",
    "previewshut",
    # Documentation/page titles
    "documentation",
    "bienvenue",
    "basics",
    "docs",
    "forge",
    "moderation",
    # Headline verbs/nouns
    "hackathon",
    "recap",
    "agreement",
    "license",
    "community",
    "responsible",
    "validate",
    "partners",
    "prompting",
    "capabilities",
    "raises",
    "studio",
    "tailor",
    "entered",
    "introducing",
    "arrives",
    "suggests",
    "temporarily",
    "unavailable",
    "capacity",
    "issues",
    "increased",
    "slower",
    "impact",
    "grants",
    "inference",
    "returns",
    "options",
    "including",
    "forward",
    "artificial",
    "frontier",
    "improve",
    "products",
    "models",
    "herd",
    "look",
    "support",
    "show",
    "promise",
    "build",
    "create",
    "driven",
    "sap",
    "instant",
    "enterprise",
    "got",
}

# Brand names — used to detect bare brand names and duplicate-brand concatenation
_BRAND_NAMES = {
    "gemini",
    "claude",
    "gpt",
    "grok",
    "llama",
    "mistral",
    "codestral",
    "pixtral",
    "command",
}


def validate_model_slug(slug: str) -> str | None:
    """Validate that a string is plausibly an AI model name.

    Returns the slug unchanged if valid, None if it looks like a
    programming language, repository path, aggregate label, or other
    non-model string.
    """
    if not slug or len(slug) < 2 or len(slug) > 100:
        return None

    normalized = slug.strip().lower()

    # Blocklist check
    if normalized in _NON_MODEL_BLOCKLIST:
        return None

    # Purely numeric strings (row IDs, ranks, measure IDs)
    if normalized.isdigit():
        return None

    # Repository paths (contains "/")
    if "/" in slug:
        return None

    # Bare year labels
    if _BARE_YEAR_RE.match(normalized):
        return None

    # Single generic word that isn't a model name
    if normalized in {"model", "test", "benchmark", "score", "rank", "result", "output"}:
        return None

    # Slugs with spaces or parentheses are raw table text, not proper model slugs
    if " " in slug or "(" in slug or ")" in slug:
        return None

    # Contains pricing/feature/headline poison words
    slug_words = set(re.split(r"[\s\-]+", normalized))
    if slug_words & _SLUG_POISON_WORDS:
        return None

    # Brand name appears more than once (concatenation artifact)
    for brand in _BRAND_NAMES:
        if normalized.count(brand) > 1:
            return None

    # Bare brand or company name without a model identifier
    if normalized in _BRAND_NAMES or normalized in {
        "mistral-ai",
        "mistral-code",
        "mistral-has",
        "openai",
        "anthropic",
        "google",
        "meta",
    }:
        return None

    return slug


async def cleanup_invalid_slugs(session: AsyncSession) -> dict[str, int]:
    """Null out invalid model_slugs on existing EventRecords and remove orphaned xrefs.

    Returns counts: {"slugs_cleaned": N, "xrefs_removed": N}.
    """
    from sqlalchemy import or_, select, update

    from ..models.events import CrossReference, EventRecord

    # Step 1: Find and null out invalid model_slugs
    result = await session.execute(
        select(EventRecord.model_slug).where(EventRecord.model_slug.is_not(None)).distinct()
    )
    all_slugs = [row[0] for row in result.all()]
    invalid_slugs = [s for s in all_slugs if validate_model_slug(s) is None]

    slugs_cleaned = 0
    if invalid_slugs:
        id_result = await session.execute(
            select(EventRecord.id).where(EventRecord.model_slug.in_(invalid_slugs))
        )
        slugs_cleaned = len(id_result.all())
        await session.execute(
            update(EventRecord)
            .where(EventRecord.model_slug.in_(invalid_slugs))
            .values(model_slug=None)
        )

    # Step 2: Remove cross-references where EITHER endpoint has a null model_slug.
    # These can't contribute meaningful "related model" links.
    all_null_result = await session.execute(
        select(EventRecord.id).where(EventRecord.model_slug.is_(None))
    )
    null_slug_ids = {row[0] for row in all_null_result.all()}

    orphaned_xrefs: list = []
    if null_slug_ids:
        xref_result = await session.execute(
            select(CrossReference).where(
                or_(
                    CrossReference.record_a_id.in_(null_slug_ids),
                    CrossReference.record_b_id.in_(null_slug_ids),
                )
            )
        )
        orphaned_xrefs = list(xref_result.scalars().all())
        for xref in orphaned_xrefs:
            await session.delete(xref)

    await session.flush()
    return {
        "slugs_cleaned": slugs_cleaned,
        "xrefs_removed": len(orphaned_xrefs),
    }


async def cleanup_lmarena_data(session: AsyncSession) -> dict[str, int]:
    """Delete all LMArena event records and their associated claims and xrefs.

    Returns counts: {"events_deleted": N, "claims_deleted": N, "xrefs_deleted": N}.
    """
    from sqlalchemy import delete, func, or_, select

    from ..models.events import ClaimRecord, CrossReference, EventRecord

    # Find all LMArena event IDs
    result = await session.execute(
        select(EventRecord.id).where(EventRecord.organization == "LMArena")
    )
    event_ids = [row[0] for row in result.all()]

    if not event_ids:
        return {"events_deleted": 0, "claims_deleted": 0, "xrefs_deleted": 0}

    # Delete cross-references involving these events
    xref_result = await session.execute(
        select(func.count())
        .select_from(CrossReference)
        .where(
            or_(
                CrossReference.record_a_id.in_(event_ids),
                CrossReference.record_b_id.in_(event_ids),
            )
        )
    )
    xrefs_count = xref_result.scalar() or 0
    await session.execute(
        delete(CrossReference).where(
            or_(
                CrossReference.record_a_id.in_(event_ids),
                CrossReference.record_b_id.in_(event_ids),
            )
        )
    )

    # Delete claims for these events
    claims_result = await session.execute(
        select(func.count()).select_from(ClaimRecord).where(ClaimRecord.event_id.in_(event_ids))
    )
    claims_count = claims_result.scalar() or 0
    await session.execute(delete(ClaimRecord).where(ClaimRecord.event_id.in_(event_ids)))

    # Delete the events themselves
    await session.execute(delete(EventRecord).where(EventRecord.organization == "LMArena"))

    await session.flush()
    return {
        "events_deleted": len(event_ids),
        "claims_deleted": claims_count,
        "xrefs_deleted": xrefs_count,
    }


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
    # ISO 8601 with time component: 2026-03-29T15:00:00Z
    match = re.search(r"(\d{4}-\d{2}-\d{2})T", text)
    if match:
        return match.group(1)

    # Standard ISO date
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
    # Semantic Scholar: API endpoint used for metadata confirmation stays high_secondary;
    # paper_discovery output (new papers surfaced by enrichment) is treated as low_discovery.
    ("Semantic Scholar", "api endpoint"): "high_secondary",
    ("Semantic Scholar", "paper_discovery"): "low_discovery",
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
