"""Model slug discovery queue — triggers follow-up searches for new models."""

from __future__ import annotations

from datetime import datetime, timezone, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.discovery import FollowUpTask
from ..models.events import EventRecord

# Task types created for each new model slug
FOLLOW_UP_TASK_TYPES = [
    "pricing_search",
    "release_notes_search",
    "system_card_search",
    "benchmark_coverage_search",
]


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


async def execute_follow_up_tasks(session: AsyncSession, limit: int = 20) -> int:
    """Execute pending follow-up tasks. Returns the number completed.

    Each task type triggers a targeted search for the model slug:
    - pricing_search: check the org's pricing page for the model
    - release_notes_search: check changelogs/release notes
    - system_card_search: check system card pages
    - benchmark_coverage_search: check benchmark leaderboards

    For now, marks tasks as completed. Full search integration
    requires the scheduling layer to dispatch actual page fetches.
    """
    result = await session.execute(
        select(FollowUpTask)
        .where(FollowUpTask.status == "pending")
        .order_by(FollowUpTask.created_at.asc())
        .limit(limit)
    )
    tasks = list(result.scalars().all())
    completed = 0

    for task in tasks:
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
