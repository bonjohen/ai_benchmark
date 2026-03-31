"""Model registry: curated model entities derived from event data."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from ...models.events import ClaimRecord, EventRecord
from ..models import ModelEntity, ModelEntitySlug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Organizations that create models vs. those that report on them.
_PUBLISHER_ORGS = frozenset(
    {
        "Anthropic",
        "OpenAI",
        "Google",
        "Google Gemini API / Google DeepMind",
        "Meta",
        "Meta Open Source AI",
        "xAI",
        "Mistral AI",
        "Cohere",
    }
)

# Date-suffix pattern for versioned API slugs (e.g., claude-3-5-sonnet-20241022).
_DATE_SUFFIX_RE = re.compile(r"-(\d{8})(-thinking-\d+k)?$")

# Infer publisher from model slug prefix patterns.
_SLUG_PUBLISHER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^claude[-_]"), "Anthropic"),
    (re.compile(r"^gpt[-_]|^chatgpt[-_]|^o[134][-_]"), "OpenAI"),
    (re.compile(r"^gemini[-_]|^gemma[-_]|^palm[-_]"), "Google"),
    (re.compile(r"^llama[-_]"), "Meta"),
    (re.compile(r"^grok[-_]"), "xAI"),
    (re.compile(r"^mistral[-_]|^codestral[-_]|^pixtral[-_]|^ministral[-_]"), "Mistral AI"),
    (re.compile(r"^command[-_]|^c4ai[-_]|^aya[-_]"), "Cohere"),
    (re.compile(r"^deepseek[-_]"), "DeepSeek"),
    (re.compile(r"^qwen|^qwq"), "Alibaba"),
    (re.compile(r"^phi[-_]"), "Microsoft"),
    (re.compile(r"^amazon[-_]|^nova[-_]"), "Amazon"),
    (re.compile(r"^yi[-_]"), "01.AI"),
    (re.compile(r"^dbrx"), "Databricks"),
    (re.compile(r"^falcon[-_]"), "TII"),
    (re.compile(r"^internlm"), "Shanghai AI Lab"),
    (re.compile(r"^chatglm|^glm[-_]"), "Zhipu AI"),
    (re.compile(r"^vicuna[-_]"), "LMSYS"),
    (re.compile(r"^wizardlm"), "Microsoft"),
    (re.compile(r"^nemotron|^nvidia[-_]|^nvila"), "NVIDIA"),
    (re.compile(r"^reka[-_]"), "Reka"),
    (re.compile(r"^jamba[-_]"), "AI21 Labs"),
    (re.compile(r"^ernie[-_]"), "Baidu"),
    (re.compile(r"^hunyuan[-_]"), "Tencent"),
    (re.compile(r"^granite[-_]|^ibm[-_]"), "IBM"),
    (re.compile(r"^kimi[-_]"), "Moonshot AI"),
    (re.compile(r"^minimax[-_]"), "MiniMax"),
    (re.compile(r"^kling[-_]|^kat[-_]"), "Kuaishou"),
    (re.compile(r"^step[-_]"), "StepFun"),
    (re.compile(r"^sora[-_]"), "OpenAI"),
    (re.compile(r"^veo[-_]"), "Google"),
    (re.compile(r"^flux[-_]"), "Black Forest Labs"),
    (re.compile(r"^runway[-_]"), "Runway"),
    (re.compile(r"^seedream[-_]|^dola[-_]"), "ByteDance"),
    (re.compile(r"^smollm|^zephyr[-_]"), "Hugging Face"),
    (re.compile(r"^cogvlm"), "Zhipu AI"),
    (re.compile(r"^rwkv[-_]"), "RWKV Foundation"),
    (re.compile(r"^stablelm"), "Stability AI"),
    (re.compile(r"^snowflake[-_]"), "Snowflake"),
    (re.compile(r"^solar[-_]"), "Upstage"),
    (re.compile(r"^starling[-_]|^athene[-_]"), "Nexusflow"),
    (re.compile(r"^olmo[-_]|^tulu[-_]|^molmo[-_]"), "AI2"),
    (re.compile(r"^mpt[-_]|^dolly[-_]"), "Databricks"),
    (re.compile(r"^openchat[-_]"), "OpenChat"),
    (re.compile(r"^openhermes[-_]|^nous[-_]"), "Nous Research"),
    (re.compile(r"^dolphin[-_]"), "Eric Hartford"),
    (re.compile(r"^stripedhyena"), "Together AI"),
    (re.compile(r"^ppl[-_]|^sonar[-_]"), "Perplexity"),
    (re.compile(r"^mercury"), "Inception Labs"),
    (re.compile(r"^mimo[-_]"), "Xiaomi"),
    (re.compile(r"^minicpm"), "OpenBMB"),
    (re.compile(r"^llava[-_]"), "LLaVA Team"),
    (re.compile(r"^internvl"), "Shanghai AI Lab"),
    (re.compile(r"^mai[-_]"), "Microsoft"),
    (re.compile(r"^ling[-_]|^ring[-_]"), "Ant Group"),
    (re.compile(r"^wan\d"), "Alibaba"),
    (re.compile(r"^devstral[-_]|^magistral[-_]|^mixtral[-_]"), "Mistral AI"),
    (re.compile(r"^codellama[-_]"), "Meta"),
    (re.compile(r"^vidu[-_]"), "Shengshu Technology"),
]

# Direct slug-to-publisher for models that can't be pattern-matched.
_SLUG_PUBLISHER_DIRECT: dict[str, str] = {
    "alpaca-13b": "Stanford",
    "diffbot-small-xl": "Diffbot",
    "intellect-3": "Intellect",
    "longcat-flash-chat": "Meituan",
    "guanaco-33b": "University of Washington",
    "koala-13b": "UC Berkeley",
    "oasst-pythia-12b": "OpenAssistant",
    "fastchat-t5-3b": "LMSYS",
    "gpt4all-13b-snoozy": "Nomic AI",
    "reve-v1.5": "Reve AI",
    "trinity-large": "Arcee AI",
    "llama2-70b-steerlm-chat": "NVIDIA",
    "KAT-Coder-Pro-V1": "Kuaishou",
    "RWKV-4-Raven-14B": "RWKV Foundation",
    "Arctic": "Snowflake",
    "INTELLECT-3": "Prime Intellect",
    "K-EXAONE": "LG AI Research",
    "LFM2.5-1.2B-Thinking": "Liquid AI",
    "Motif-2-12.7B": "Motif AI",
    "Nanbeige4.1-3B": "Nanbeige",
    "Seed-OSS-36B-Instruct": "ByteDance",
}


def _prettify_slug(slug: str) -> str:
    """Convert a model slug to a human-readable display name."""
    return slug.replace("-", " ").replace("_", " ").title()


def _strip_date_suffix(slug: str) -> str | None:
    """Strip a -YYYYMMDD suffix from a slug. Returns base slug or None if no match."""
    m = _DATE_SUFFIX_RE.search(slug)
    if m:
        return slug[: m.start()]
    return None


def _is_publisher(org: str) -> bool:
    """Check if an organization is a model publisher."""
    return org in _PUBLISHER_ORGS


def _infer_publisher_from_slug(slug: str) -> str | None:
    """Infer the model publisher from the slug name pattern."""
    # Direct lookup first (handles irregular names)
    if slug in _SLUG_PUBLISHER_DIRECT:
        return _SLUG_PUBLISHER_DIRECT[slug]
    slug_lower = slug.lower()
    for pattern, publisher in _SLUG_PUBLISHER_PATTERNS:
        if pattern.search(slug_lower):
            return publisher
    return None


def _infer_status(event_types: set[str]) -> str:
    """Infer model status from its event types."""
    if "deprecation" in event_types:
        return "deprecated"
    if "model_release" in event_types or "api_update" in event_types:
        return "active"
    return "announced"


async def seed_model_entities(session: AsyncSession) -> dict[str, int]:
    """Populate model_entities and model_entity_slugs from event data.

    Returns stats dict with counts of entities created, slugs mapped, etc.
    """
    # Clear existing registry data for a clean reseed
    await session.execute(delete(ModelEntitySlug))
    await session.execute(delete(ModelEntity))
    await session.flush()

    # Load all distinct (model_slug, organization) pairs with event type info
    stmt = (
        select(
            EventRecord.model_slug,
            EventRecord.organization,
            func.group_concat(EventRecord.event_type.distinct()).label("event_types"),
            func.min(EventRecord.published_date).label("first_date"),
        )
        .where(EventRecord.model_slug.is_not(None))
        .group_by(EventRecord.model_slug, EventRecord.organization)
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Phase 1: Create entities from publisher-sourced slugs
    entities: dict[str, ModelEntity] = {}  # canonical_slug → entity
    slug_mappings: list[tuple[str, str, str]] = []  # (slug, org, canonical_slug)

    publisher_rows = [(r[0], r[1], r[2], r[3]) for r in rows if _is_publisher(r[1])]
    aggregator_rows = [(r[0], r[1], r[2], r[3]) for r in rows if not _is_publisher(r[1])]

    for slug, org, event_types_str, first_date in publisher_rows:
        event_types = set((event_types_str or "").split(","))
        canonical = slug
        status = _infer_status(event_types)

        if canonical not in entities:
            entities[canonical] = ModelEntity(
                canonical_slug=canonical,
                display_name=_prettify_slug(canonical),
                publisher=org,
                status=status,
                release_date=first_date,
            )
        slug_mappings.append((slug, org, canonical))

    # Phase 2: Map aggregator slugs to existing entities or create new ones
    for slug, org, event_types_str, first_date in aggregator_rows:
        # Try exact match
        if slug in entities:
            slug_mappings.append((slug, org, slug))
            continue

        # Try stripping date suffix
        base = _strip_date_suffix(slug)
        if base and base in entities:
            slug_mappings.append((slug, org, base))
            continue

        # No match — create a new entity, infer publisher from slug name
        if slug not in entities:
            event_types = set((event_types_str or "").split(","))
            inferred_pub = _infer_publisher_from_slug(slug) or "Unknown"
            entities[slug] = ModelEntity(
                canonical_slug=slug,
                display_name=_prettify_slug(slug),
                publisher=inferred_pub,
                status=_infer_status(event_types),
                release_date=first_date,
            )
        slug_mappings.append((slug, org, slug))

    # Phase 3: Persist entities
    for entity in entities.values():
        session.add(entity)
    await session.flush()

    # Phase 4: Persist slug mappings
    seen_slug_org: set[tuple[str, str]] = set()
    slugs_created = 0
    for slug, org, canonical in slug_mappings:
        key = (slug, org)
        if key in seen_slug_org:
            continue
        seen_slug_org.add(key)
        entity = entities[canonical]
        session.add(
            ModelEntitySlug(
                entity_id=entity.id,
                event_slug=slug,
                source_org=org,
            )
        )
        slugs_created += 1
    await session.flush()

    return {
        "entities_created": len(entities),
        "slugs_mapped": slugs_created,
        "publisher_sourced": len(publisher_rows),
        "aggregator_sourced": len(aggregator_rows),
    }


async def list_model_entities(
    session: AsyncSession,
    *,
    publisher: str | None = None,
    status: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[ModelEntity]:
    """Query curated model entities for the list page."""
    stmt = select(ModelEntity).order_by(ModelEntity.display_name).offset(offset).limit(limit)
    if publisher:
        stmt = stmt.where(ModelEntity.publisher == publisher)
    if status:
        stmt = stmt.where(ModelEntity.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_model_entity(session: AsyncSession, canonical_slug: str) -> ModelEntity | None:
    """Look up a single model entity by canonical slug."""
    stmt = select(ModelEntity).where(ModelEntity.canonical_slug == canonical_slug)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_entity_events(session: AsyncSession, entity_id: int) -> list[EventRecord]:
    """Get all events across all slug variants for a model entity."""
    # Get all mapped slugs
    slug_stmt = select(ModelEntitySlug.event_slug).where(ModelEntitySlug.entity_id == entity_id)
    slug_result = await session.execute(slug_stmt)
    slugs = [r[0] for r in slug_result.all()]

    if not slugs:
        return []

    event_stmt = (
        select(EventRecord)
        .where(EventRecord.model_slug.in_(slugs))
        .order_by(EventRecord.observed_at.desc())
    )
    result = await session.execute(event_stmt)
    return list(result.scalars().all())


async def get_entity_claims(session: AsyncSession, entity_id: int) -> list[ClaimRecord]:
    """Get all claims for events belonging to a model entity."""
    slug_stmt = select(ModelEntitySlug.event_slug).where(ModelEntitySlug.entity_id == entity_id)
    slug_result = await session.execute(slug_stmt)
    slugs = [r[0] for r in slug_result.all()]

    if not slugs:
        return []

    claim_stmt = (
        select(ClaimRecord)
        .join(EventRecord, ClaimRecord.event_id == EventRecord.id)
        .where(EventRecord.model_slug.in_(slugs))
        .order_by(ClaimRecord.observed_at.desc())
    )
    result = await session.execute(claim_stmt)
    return list(result.scalars().all())


async def count_model_entities(session: AsyncSession) -> int:
    """Count total curated model entities."""
    result = await session.execute(select(func.count(ModelEntity.id)))
    return result.scalar_one()


async def list_publishers(session: AsyncSession) -> list[str]:
    """Get distinct publisher names for filter dropdowns."""
    stmt = select(ModelEntity.publisher).distinct().order_by(ModelEntity.publisher)
    result = await session.execute(stmt)
    return [r[0] for r in result.all()]
