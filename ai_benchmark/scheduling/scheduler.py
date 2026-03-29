"""APScheduler integration — async scheduler for collection pipeline.

Supports cron-based triggers per source, concurrency control,
error tracking with circuit breaker, and health monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone, UTC
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..collection.fetcher import Fetcher
from ..collection.snapshot import SnapshotManager
from ..config.settings import PipelineSettings, load_source_catalog
from ..models.base import create_engine, create_session_factory
from ..processing.pipeline import process_items
from ..sources.registry import get_collector
from .cadence import ScheduleEntry, load_schedules, parse_cron_fields

logger = structlog.get_logger()

# Circuit breaker: skip a source after this many consecutive failures
MAX_CONSECUTIVE_FAILURES = 5


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
        return self._state.get(organization, {
            "last_success_at": None,
            "last_failure_at": None,
            "consecutive_failures": 0,
        })

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        return dict(self._state)


class PipelineScheduler:
    """Manages scheduled collection jobs for all sources."""

    def __init__(self, settings: PipelineSettings) -> None:
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self.health = SourceHealthTracker()
        self._fetcher: Fetcher | None = None
        self._session_factory = None

    async def setup(self) -> None:
        """Initialize database and HTTP client."""
        engine = create_engine(self.settings.database_url)
        self._session_factory = create_session_factory(engine)
        self._fetcher = Fetcher(
            user_agent=self.settings.user_agent,
            timeout=self.settings.request_timeout,
            max_concurrency=self.settings.max_concurrency,
            retry_attempts=self.settings.retry_attempts,
        )

    async def collect_source(self, organization: str) -> None:
        """Run collection for a single source organization."""
        log = logger.bind(organization=organization)

        if self.health.is_circuit_open(organization):
            log.warning("circuit_open", msg="Skipping due to consecutive failures")
            return

        try:
            sources = load_source_catalog()
            source_config = next(
                (s for s in sources if s.organization == organization), None
            )
            if not source_config:
                log.error("source_not_found")
                return

            collector = get_collector(
                source_config, github_token=self.settings.github_token
            )
            snapshot_mgr = SnapshotManager(self._session_factory)

            all_items = []
            for page in collector.get_pages():
                try:
                    items, _diff = await collector.collect_page(
                        page, self._fetcher, snapshot_mgr, page_id=0
                    )
                    all_items.extend(items)
                except Exception as e:
                    log.warning("page_error", page=page.canonical_url, error=str(e))

            if all_items:
                async with self._session_factory() as session, session.begin():
                    await process_items(
                        session, all_items,
                        source_id=0, page_id=None,
                        organization=organization,
                        source_type=source_config.classification,
                        classification=source_config.classification,
                    )

            self.health.record_success(organization)
            log.info("collection_complete", items=len(all_items))

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
