"""Schedule cadence configuration — loads cron expressions from schedules.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScheduleEntry:
    """A single source polling schedule."""

    organization: str
    cron: str
    max_concurrent: int = 1


def load_schedules(path: Path | None = None) -> list[ScheduleEntry]:
    """Load schedule entries from TOML file."""
    if path is None:
        path = Path(__file__).parent.parent / "config" / "schedules.toml"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [
        ScheduleEntry(
            organization=entry["organization"],
            cron=entry["cron"],
            max_concurrent=entry.get("max_concurrent", 1),
        )
        for entry in data.get("schedules", [])
    ]


def parse_cron_fields(cron: str) -> dict[str, str]:
    """Parse a cron expression into APScheduler trigger fields."""
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }
