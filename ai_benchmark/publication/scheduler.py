"""Publication scheduler integration — daily edition generation job."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ..config.settings import PipelineSettings

logger = structlog.get_logger(__name__)


class PublicationHealthTracker:
    """Tracks publication job health and failure state."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {
            "last_generated_at": None,
            "last_publication_date": None,
            "last_error": None,
            "last_failure_at": None,
            "consecutive_failures": 0,
            "total_runs": 0,
            "total_successes": 0,
        }

    def record_success(self, publication_date: str) -> None:
        self._state["last_generated_at"] = datetime.now(UTC)
        self._state["last_publication_date"] = publication_date
        self._state["last_error"] = None
        self._state["consecutive_failures"] = 0
        self._state["total_runs"] += 1
        self._state["total_successes"] += 1

    def record_failure(self, error: str) -> None:
        self._state["last_failure_at"] = datetime.now(UTC)
        self._state["last_error"] = error
        self._state["consecutive_failures"] += 1
        self._state["total_runs"] += 1

    def get_status(self) -> dict[str, Any]:
        return dict(self._state)


async def run_publication_job(settings: PipelineSettings) -> dict[str, Any]:
    """Execute the daily publication job.

    Creates the engine, generates the edition for today, optionally
    exports static files, and returns a summary dict.

    Publication failures do not propagate — they are caught, logged,
    and recorded in the health tracker. This ensures the base
    collection pipeline is never blocked.
    """
    from ..models.base import Base, create_engine, create_session_factory
    from .config import PublicationSettings
    from .services.edition import generate_edition

    pub_settings = PublicationSettings()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    engine = create_engine(settings.database_url)
    # Register all models
    from ..analysis import models as analysis_models  # noqa: F401
    from ..models import discovery, events, research, sources  # noqa: F401
    from . import models as publication_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            result = await generate_edition(session, publication_date=today, settings=pub_settings)
            await session.commit()

        logger.info(
            "publication_job_complete",
            date=today,
            entries=result.stats.get("total_entries", 0),
            candidates=result.stats.get("total_candidates", 0),
        )

        # Static export if configured
        if pub_settings.export_path:
            from .services.export import export_static

            written = await export_static(result, pub_settings.export_path)
            logger.info("publication_static_export", files=written)

        return {
            "status": "success",
            "publication_date": today,
            "edition_id": result.edition_id,
            "total_entries": result.stats.get("total_entries", 0),
        }

    except Exception as e:
        logger.error("publication_job_failed", date=today, error=str(e))
        return {
            "status": "failure",
            "publication_date": today,
            "error": str(e),
        }

    finally:
        await engine.dispose()


def add_publication_job(
    scheduler_instance,
    settings: PipelineSettings,
    health: PublicationHealthTracker,
    cron: str = "0 7 * * *",
) -> None:
    """Register the daily publication job on an APScheduler instance.

    Args:
        scheduler_instance: APScheduler AsyncIOScheduler.
        settings: Pipeline settings for DB access.
        health: Health tracker to record success/failure.
        cron: Cron expression for the job (default: daily at 7 AM).
    """
    from apscheduler.triggers.cron import CronTrigger

    from ..scheduling.cadence import parse_cron_fields

    cron_fields = parse_cron_fields(cron)
    trigger = CronTrigger(**cron_fields)

    async def _job():
        result = await run_publication_job(settings)
        if result["status"] == "success":
            health.record_success(result["publication_date"])
        else:
            health.record_failure(result.get("error", "unknown"))

    scheduler_instance.add_job(
        _job,
        trigger=trigger,
        id="publication_daily",
        name="Daily Publication",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("publication_job_registered", cron=cron)
