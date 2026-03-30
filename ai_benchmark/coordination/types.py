"""Data types for the collection coordinator: FetchTask and CoordFetchResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime


@dataclass(frozen=True, slots=True)
class FetchTask:
    """Immutable description of a page to fetch. Created by the coordinator, consumed by workers."""

    task_id: str
    organization: str
    page_url: str
    page_type: str
    page_id: int | None
    source_id: int
    classification: str
    collector_class_name: str
    css_selectors: dict[str, str] = field(default_factory=dict)
    since_date: date | None = None
    priority: bool = False
    attempt: int = 0


@dataclass(slots=True)
class CoordFetchResult:
    """Result of a worker's fetch-and-extract cycle. Consumed by the coordinator."""

    task_id: str
    organization: str
    page_url: str
    page_type: str
    page_id: int | None
    source_id: int
    classification: str
    items: list = field(default_factory=list)
    html_content: str = ""
    fetch_status: int = 0
    fetch_error: str | None = None
    elapsed_ms: float = 0.0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    css_selectors: dict[str, str] = field(default_factory=dict)
    has_custom_collect: bool = False
    since_date: date | None = None
    priority: bool = False
    attempt: int = 0
