"""Integration tests for the collection pipeline.

Tests the coordinator -> worker -> snapshot -> pipeline chain
with mocked HTTP, verifying end-to-end event creation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from ai_benchmark.config.settings import PageConfig, PipelineSettings, SourceConfig
from ai_benchmark.coordination.coordinator import CollectionCoordinator
from ai_benchmark.models.base import create_session_factory
from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Snapshot, Source
from ai_benchmark.sources.base import RawItem


def _make_source_config(org: str = "TestOrg") -> SourceConfig:
    """Build a minimal SourceConfig for testing."""
    return SourceConfig(
        source_name=f"{org} Source",
        category="vendor",
        organization=org,
        homepage_url=f"https://{org.lower()}.example.com",
        base_domain=f"{org.lower()}.example.com",
        trust_rating=5.0,
        source_role="official announcements",
        classification="primary",
        collection_method="html",
        pages=[
            PageConfig(
                canonical_url=f"https://{org.lower()}.example.com/models",
                page_type="model_catalog",
            ),
        ],
    )


async def _seed_source(session, org: str = "TestOrg") -> tuple[Source, Page]:
    """Insert a Source and Page row and return both."""
    source = Source(
        source_name=f"{org} Source",
        category="vendor",
        organization=org,
        homepage_url=f"https://{org.lower()}.example.com",
        base_domain=f"{org.lower()}.example.com",
        trust_rating=5.0,
        source_role="official announcements",
        classification="primary",
        collection_method="html",
    )
    session.add(source)
    await session.flush()

    page = Page(
        source_id=source.id,
        canonical_url=f"https://{org.lower()}.example.com/models",
        page_type="model_catalog",
    )
    session.add(page)
    await session.flush()
    return source, page


def _make_fetch_result(body: str = "<html><body>Test</body></html>", status: int = 200):
    """Create a mock HTTP fetch result."""
    from datetime import UTC, datetime

    result = MagicMock()
    result.url = "https://test.example.com"
    result.status_code = status
    result.headers = {}
    result.body_text = body
    result.elapsed_ms = 100.0
    result.fetched_at = datetime.now(UTC)
    result.error = None
    result.ok = 200 <= status < 400
    return result


@pytest.mark.asyncio
class TestCollectionCoordinatorIntegration:
    """Integration tests for the coordinator -> worker -> pipeline chain."""

    async def test_full_path_items_extracted_and_processed(self, db_engine):
        """End-to-end: collect_all extracts items, process_items creates events."""
        session_factory = create_session_factory(db_engine)

        # Seed database
        async with session_factory() as session:
            source, page = await _seed_source(session)
            source_id = source.id
            page_id = page.id
            await session.commit()

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        coord = CollectionCoordinator(settings)
        coord._session_factory = session_factory
        coord._engine = MagicMock()

        source_config = _make_source_config("TestOrg")

        # Fake items the collector will return
        fake_items = [
            RawItem(
                title="TestOrg Launches SuperModel v2",
                url="https://testorg.example.com/models/v2",
                body="SuperModel v2 released with improved reasoning",
                item_type="model_release",
                model_hint="supermodel-v2",
            ),
            RawItem(
                title="TestOrg Updates Pricing for Q3",
                url="https://testorg.example.com/pricing",
                body="New pricing tiers announced",
                item_type="pricing_change",
            ),
        ]

        # Mock collector
        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.extract_items.return_value = fake_items

        # Mock fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=_make_fetch_result())
        coord._fetcher = mock_fetcher

        with (
            patch(
                "ai_benchmark.coordination.coordinator.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.coordination.worker.get_collector",
                return_value=mock_collector,
            ),
        ):
            stats = await coord.collect_all(organizations=["TestOrg"])

        assert stats["tasks_created"] == 1
        assert stats["items_processed"] == 2

        # Verify events were created in the database
        async with session_factory() as session:
            result = await session.execute(select(EventRecord))
            events = list(result.scalars().all())
            assert len(events) == 2, f"Expected 2 events, got {len(events)}"

            # First event should have model slug extracted
            model_event = next(e for e in events if e.model_slug == "supermodel-v2")
            assert model_event.organization == "TestOrg"
            assert model_event.source_type == "primary"
            assert model_event.source_id == source_id

            # Verify claims were created for each event
            claims_result = await session.execute(select(ClaimRecord))
            claims = list(claims_result.scalars().all())
            assert len(claims) == 2

            # Verify page metadata was updated
            page_result = await session.execute(select(Page).where(Page.id == page_id))
            page_record = page_result.scalar_one()
            assert page_record.times_polled >= 1
            assert page_record.last_polled_at is not None

    async def test_collection_with_no_items(self, db_engine):
        """When the collector returns no items, no events are created."""
        session_factory = create_session_factory(db_engine)

        async with session_factory() as session:
            await _seed_source(session)
            await session.commit()

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        coord = CollectionCoordinator(settings)
        coord._session_factory = session_factory
        coord._engine = MagicMock()

        source_config = _make_source_config("TestOrg")

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.extract_items.return_value = []

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=_make_fetch_result())
        coord._fetcher = mock_fetcher

        with (
            patch(
                "ai_benchmark.coordination.coordinator.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.coordination.worker.get_collector",
                return_value=mock_collector,
            ),
        ):
            stats = await coord.collect_all(organizations=["TestOrg"])

        assert stats["tasks_completed"] == 1
        assert stats["items_processed"] == 0

        # Verify no events in the database
        async with session_factory() as session:
            result = await session.execute(select(EventRecord))
            events = list(result.scalars().all())
            assert len(events) == 0

    async def test_empty_catalog_returns_no_tasks(self, db_engine):
        """When the source org is not in the catalog, no tasks are created."""
        session_factory = create_session_factory(db_engine)

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        coord = CollectionCoordinator(settings)
        coord._session_factory = session_factory
        coord._engine = MagicMock()
        coord._fetcher = AsyncMock()

        with patch(
            "ai_benchmark.coordination.coordinator.load_source_catalog",
            return_value=[_make_source_config("OtherOrg")],
        ):
            stats = await coord.collect_all(organizations=["NonExistentOrg"])

        assert stats["tasks_created"] == 0
        assert stats["items_processed"] == 0

    async def test_fetch_failure_records_error(self, db_engine):
        """When fetch fails, the coordinator increments consecutive_failures."""
        session_factory = create_session_factory(db_engine)

        async with session_factory() as session:
            _source, page = await _seed_source(session)
            page_id = page.id
            await session.commit()

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        coord = CollectionCoordinator(settings)
        coord._session_factory = session_factory
        coord._engine = MagicMock()

        source_config = _make_source_config("TestOrg")

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages

        # Fetcher returns an error
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=_make_fetch_result(status=500))
        # Make the error result have ok=False
        mock_fetcher.fetch.return_value.ok = False
        mock_fetcher.fetch.return_value.error = "Internal Server Error"
        coord._fetcher = mock_fetcher

        with (
            patch(
                "ai_benchmark.coordination.coordinator.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.coordination.worker.get_collector",
                return_value=mock_collector,
            ),
        ):
            stats = await coord.collect_all(organizations=["TestOrg"])

        assert stats["tasks_failed"] >= 1

        # Page should have consecutive_failures incremented
        async with session_factory() as session:
            page_result = await session.execute(select(Page).where(Page.id == page_id))
            page_record = page_result.scalar_one()
            assert page_record.consecutive_failures >= 1

    async def test_snapshot_created_during_collection(self, db_engine):
        """Verify that snapshot records are created via SnapshotManager."""
        session_factory = create_session_factory(db_engine)

        async with session_factory() as session:
            _source, page = await _seed_source(session)
            page_id = page.id
            await session.commit()

        source_config = _make_source_config("TestOrg")

        fake_items = [
            RawItem(
                title="TestOrg Releases Model Alpha",
                url="https://testorg.example.com/alpha",
                body="Model Alpha is live",
                item_type="model_release",
                model_hint="model-alpha",
            ),
        ]

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.extract_items.return_value = fake_items

        html_content = "<html><body>Model Alpha content</body></html>"
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=_make_fetch_result(body=html_content))

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        coord = CollectionCoordinator(settings)
        coord._session_factory = session_factory
        coord._engine = MagicMock()
        coord._fetcher = mock_fetcher

        with (
            patch(
                "ai_benchmark.coordination.coordinator.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.coordination.worker.get_collector",
                return_value=mock_collector,
            ),
        ):
            stats = await coord.collect_all(organizations=["TestOrg"])

        assert stats["items_processed"] == 1

        # Verify snapshot was stored (SnapshotManager.compare_with_latest stores it)
        async with session_factory() as session:
            snap_result = await session.execute(select(Snapshot).where(Snapshot.page_id == page_id))
            snapshots = list(snap_result.scalars().all())
            assert len(snapshots) == 1

            # Event should also exist
            event_result = await session.execute(select(EventRecord))
            events = list(event_result.scalars().all())
            assert len(events) == 1
            assert events[0].model_slug == "model-alpha"
