"""APScheduler integration — async scheduler for collection pipeline.

Supports cron-based triggers per source, concurrency control,
error tracking with circuit breaker, and health monitoring.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..coordination.coordinator import CollectionCoordinator
from ..processing.normalizer import extract_date
from .cadence import ScheduleEntry, load_schedules, parse_cron_fields

if TYPE_CHECKING:
    from ..config.settings import PipelineSettings
    from ..sources.base import RawItem

logger = structlog.get_logger()

# Circuit breaker: skip a source after this many consecutive failures
MAX_CONSECUTIVE_FAILURES = 5


def _item_in_date_range(item: RawItem, since_date: date) -> bool:
    """Check if an item's date falls on or after since_date. Keeps undated items."""
    date_str = extract_date(item.date_text or item.body)
    if date_str is None:
        return True  # keep items without parseable dates
    return date_str >= since_date.isoformat()


class SourceHealthTracker:
    """Tracks per-source health and failure state."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    def record_success(self, organization: str) -> None:
        state = self._state.setdefault(organization, {})
        state["last_success_at"] = datetime.now(UTC)
        state["consecutive_failures"] = 0

    def record_failure(self, organization: str, error: str) -> None:
        state = self._state.setdefault(organization, {})
        state["last_failure_at"] = datetime.now(UTC)
        state["last_error"] = error
        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1

    def is_circuit_open(self, organization: str) -> bool:
        state = self._state.get(organization, {})
        return state.get("consecutive_failures", 0) >= MAX_CONSECUTIVE_FAILURES

    def get_status(self, organization: str) -> dict[str, Any]:
        return self._state.get(
            organization,
            {
                "last_success_at": None,
                "last_failure_at": None,
                "consecutive_failures": 0,
            },
        )

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        return dict(self._state)


class PipelineScheduler:
    """Manages scheduled collection jobs for all sources."""

    def __init__(self, settings: PipelineSettings) -> None:
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self.health = SourceHealthTracker()
        self._coordinator: CollectionCoordinator | None = None

    async def setup(self) -> None:
        """Initialize coordinator."""
        self._coordinator = CollectionCoordinator(self.settings)
        await self._coordinator.setup()

    async def collect_source(
        self,
        organization: str,
        since_date: date | None = None,
    ) -> None:
        """Run collection for a single source organization."""
        log = logger.bind(organization=organization)

        if self.health.is_circuit_open(organization):
            log.warning("circuit_open", msg="Skipping due to consecutive failures")
            return

        try:
            stats = await self._coordinator.collect_all(
                organizations=[organization],
                since_date=since_date,
            )
            self.health.record_success(organization)
            log.info(
                "collection_complete",
                items=stats["items_processed"],
                events=stats["events_created"],
            )

        except Exception as e:
            self.health.record_failure(organization, str(e))
            log.error("collection_failed", error=str(e))

    def add_schedule(self, entry: ScheduleEntry) -> None:
        """Add a cron-triggered job for a source."""
        cron_fields = parse_cron_fields(entry.cron)
        trigger = CronTrigger(**cron_fields)
        self.scheduler.add_job(
            self.collect_source,
            trigger=trigger,
            args=[entry.organization],
            id=f"collect_{entry.organization}",
            name=f"Collect {entry.organization}",
            replace_existing=True,
            max_instances=entry.max_concurrent,
        )

    def load_all_schedules(self) -> int:
        """Load all schedules from the config file."""
        entries = load_schedules()
        for entry in entries:
            self.add_schedule(entry)
        return len(entries)

    def start(self) -> None:
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("scheduler_started", jobs=len(self.scheduler.get_jobs()))

    async def shutdown_coordinator(self) -> None:
        """Shut down the coordinator (close Fetcher, dispose engine)."""
        if self._coordinator:
            await self._coordinator.shutdown()

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        self.scheduler.shutdown(wait=True)
        logger.info("scheduler_stopped")

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get info about all scheduled jobs."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]
