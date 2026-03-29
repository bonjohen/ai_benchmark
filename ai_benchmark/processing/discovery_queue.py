"""Model slug discovery queue — triggers follow-up searches for new models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..config.settings import load_source_catalog
from ..models.discovery import FollowUpTask
from ..models.events import EventRecord
from ..models.sources import Page, Source

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..collection.fetcher import Fetcher

logger = structlog.get_logger()

# Task types created for each new model slug
FOLLOW_UP_TASK_TYPES = [
    "pricing_search",
    "release_notes_search",
    "system_card_search",
    "benchmark_coverage_search",
]

# Maps each task type to the page_type substrings to match in the source catalog
_TASK_PAGE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "pricing_search": ["pricing"],
    "release_notes_search": ["changelog", "release"],
    "system_card_search": ["system-card", "system card"],
    "benchmark_coverage_search": ["leaderboard"],
}


class DiscoveryQueue:
    """Tracks known model slugs and enqueues follow-up searches for new ones."""

    def __init__(self):
        self._known_slugs: set[str] = set()
        self._initialized = False

    async def _ensure_initialized(self, session: AsyncSession) -> None:
        """Load known slugs from DB on first use."""
        if self._initialized:
            return
        result = await session.execute(
            select(EventRecord.model_slug).where(EventRecord.model_slug.is_not(None)).distinct()
        )
        self._known_slugs = {row[0] for row in result.all()}
        self._initialized = True

    async def check_new_slug(self, session: AsyncSession, model_slug: str) -> bool:
        """Returns True if slug has not been seen before; adds it to the set."""
        await self._ensure_initialized(session)
        if model_slug in self._known_slugs:
            return False
        self._known_slugs.add(model_slug)
        return True


async def enqueue_follow_up(
    session: AsyncSession,
    model_slug: str,
    organization: str,
) -> list[FollowUpTask]:
    """Create follow-up task records for a newly discovered model slug."""
    tasks = []
    for task_type in FOLLOW_UP_TASK_TYPES:
        task = FollowUpTask(
            model_slug=model_slug,
            organization=organization,
            task_type=task_type,
            status="pending",
        )
        session.add(task)
        tasks.append(task)
    await session.flush()
    return tasks


def _find_page_for_task(
    organization: str,
    task_type: str,
) -> tuple[str, str] | None:
    """Return (canonical_url, page_type) from the source catalog for the given task type.

    Loads the TOML catalog and matches the organization's pages by page_type
    keywords associated with the task type. Returns the first match, or None.
    """
    keywords = _TASK_PAGE_TYPE_KEYWORDS.get(task_type, [])
    catalog = load_source_catalog()
    for source_cfg in catalog:
        if source_cfg.organization != organization:
            continue
        for page_cfg in source_cfg.pages:
            page_type_lower = page_cfg.page_type.lower()
            if any(kw in page_type_lower for kw in keywords):
                return page_cfg.canonical_url, page_cfg.page_type
    return None


async def execute_follow_up_tasks(
    session: AsyncSession,
    fetcher: Fetcher,
    limit: int = 20,
) -> int:
    """Execute pending follow-up tasks. Returns the number completed.

    Each task type dispatches a real fetch to the org's matching page:
    - pricing_search: org's pricing page
    - release_notes_search: org's changelog/release-notes page
    - system_card_search: org's system-card page
    - benchmark_coverage_search: any leaderboard page for the org

    Fetches the page, extracts items with the org's registered collector,
    and processes them through the standard pipeline. Marks the task
    completed only after a successful fetch and process; marks it failed
    if the fetch returns an error.
    """
    # Import here to avoid circular imports at module load time
    from ..sources.registry import COLLECTOR_CLASSES
    from .pipeline import process_items

    result = await session.execute(
        select(FollowUpTask)
        .where(FollowUpTask.status == "pending")
        .order_by(FollowUpTask.created_at.asc())
        .limit(limit)
    )
    tasks = list(result.scalars().all())
    completed = 0

    for task in tasks:
        log = logger.bind(
            model_slug=task.model_slug,
            organization=task.organization,
            task_type=task.task_type,
        )

        # Find the target page from the source catalog
        page_target = _find_page_for_task(task.organization, task.task_type)
        if page_target is None:
            log.warning("follow_up_no_page_found")
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            continue

        target_url, page_type = page_target

        # Look up the Source and Page records in DB
        source_row = await session.execute(
            select(Source).where(Source.organization == task.organization).limit(1)
        )
        source_record = source_row.scalar_one_or_none()
        if source_record is None:
            log.warning("follow_up_source_not_in_db", url=target_url)
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            continue

        page_row = await session.execute(
            select(Page).where(Page.canonical_url == target_url).limit(1)
        )
        page_record = page_row.scalar_one_or_none()
        page_id = page_record.id if page_record else None

        # Fetch the page
        fetch_result = await fetcher.fetch(target_url)
        if not fetch_result.ok:
            log.warning(
                "follow_up_fetch_failed",
                url=target_url,
                status=fetch_result.status_code,
                error=fetch_result.error,
            )
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            continue

        # Extract items using the registered collector
        collector_cls = COLLECTOR_CLASSES.get(task.organization)
        if collector_cls is None:
            log.warning("follow_up_no_collector", organization=task.organization)
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            continue

        # Build a minimal PageConfig for extraction
        from ..config.settings import PageConfig

        page_cfg = PageConfig(canonical_url=target_url, page_type=page_type)

        # Build a minimal SourceConfig for collector instantiation
        from ..config.settings import SourceConfig

        source_cfg = SourceConfig(
            source_name=source_record.source_name,
            category=source_record.category,
            organization=source_record.organization,
            homepage_url=source_record.homepage_url,
            base_domain=source_record.base_domain,
            trust_rating=source_record.trust_rating,
            source_role=source_record.source_role,
            classification=source_record.classification,
            collection_method=source_record.collection_method,
            pages=[page_cfg],
        )

        collector = collector_cls(source_cfg)
        items = collector.extract_items(fetch_result.body_text, page_cfg)

        # Filter to items that mention the model slug
        slug_lower = task.model_slug.lower()
        relevant_items = [
            it for it in items if slug_lower in it.title.lower() or slug_lower in it.body.lower()
        ]

        if relevant_items:
            await process_items(
                session=session,
                items=relevant_items,
                source_id=source_record.id,
                page_id=page_id,
                organization=source_record.organization,
                source_type=page_type,
                classification=source_record.classification,
            )
            log.info("follow_up_processed", count=len(relevant_items), url=target_url)
        else:
            log.debug("follow_up_no_relevant_items", url=target_url)

        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        completed += 1

    await session.flush()
    return completed


# Module-level singleton for use in pipeline
_discovery_queue = DiscoveryQueue()


async def check_and_enqueue(
    session: AsyncSession,
    model_slug: str,
    organization: str,
) -> bool:
    """Pipeline integration: check if slug is new and enqueue follow-ups.

    Returns True if the slug was new and tasks were enqueued.
    """
    if await _discovery_queue.check_new_slug(session, model_slug):
        await enqueue_follow_up(session, model_slug, organization)
        return True
    return False
