"""Snapshot storage, retrieval, and change comparison."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sources import Page, Snapshot
from .differ import DiffResult, clean_html, diff_snapshots


def compute_content_hash(content: str) -> str:
    """SHA-256 hash of content for fast change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SnapshotManager:
    """Manages snapshot storage and comparison for a page."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_snapshot(
        self,
        page_id: int,
        content: str,
        content_hash: str | None = None,
    ) -> Snapshot:
        """Store a new snapshot for a page."""
        if content_hash is None:
            content_hash = compute_content_hash(content)
        snapshot = Snapshot(
            page_id=page_id,
            content=content,
            content_hash=content_hash,
            fetched_at=datetime.now(timezone.utc),
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_snapshot(self, page_id: int) -> Snapshot | None:
        """Get the most recent snapshot for a page."""
        result = await self.session.execute(
            select(Snapshot)
            .where(Snapshot.page_id == page_id)
            .order_by(Snapshot.fetched_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def compare_with_latest(
        self,
        page_id: int,
        new_raw_html: str,
        content_selectors: list[str] | None = None,
    ) -> tuple[DiffResult, Snapshot]:
        """Compare new content against the latest snapshot.

        Cleans the HTML, checks hash for fast no-change detection,
        runs the differ if content changed, and stores the new snapshot.

        Returns:
            Tuple of (DiffResult, new_snapshot).
        """
        cleaned = clean_html(new_raw_html, content_selectors)
        new_hash = compute_content_hash(cleaned)

        latest = await self.get_latest_snapshot(page_id)

        if latest is not None and latest.content_hash == new_hash:
            # Content unchanged — store snapshot but report no change
            snapshot = await self.store_snapshot(page_id, cleaned, new_hash)
            # Increment times_polled
            page_result = await self.session.execute(select(Page).where(Page.id == page_id))
            page_obj = page_result.scalar_one_or_none()
            if page_obj:
                page_obj.times_polled = (page_obj.times_polled or 0) + 1
                page_obj.last_polled_at = datetime.now(timezone.utc)
            return DiffResult(changed=False), snapshot

        # Content changed (or first snapshot)
        if latest is not None:
            diff = diff_snapshots(latest.content, cleaned)
        else:
            diff = DiffResult(changed=True, added_lines=cleaned.splitlines(), change_ratio=1.0)

        snapshot = await self.store_snapshot(page_id, cleaned, new_hash)

        # Update page last_changed_at
        page_result = await self.session.execute(select(Page).where(Page.id == page_id))
        page = page_result.scalar_one_or_none()
        if page:
            page.times_polled = (page.times_polled or 0) + 1
            page.last_changed_at = datetime.now(timezone.utc)
            page.last_polled_at = datetime.now(timezone.utc)

        return diff, snapshot
