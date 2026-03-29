"""Integration tests for the collection daemon path.

Tests the full scheduler -> collector -> snapshot -> pipeline chain
with mocked HTTP, verifying end-to-end event creation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from ai_benchmark.collection.differ import DiffResult
from ai_benchmark.config.settings import PageConfig, PipelineSettings, SourceConfig
from ai_benchmark.models.base import create_session_factory
from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Snapshot, Source
from ai_benchmark.scheduling.scheduler import PipelineScheduler
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


@pytest.mark.asyncio
class TestCollectionDaemonIntegration:
    """Integration tests for the scheduler -> collector -> pipeline chain."""

    async def test_full_path_items_extracted_and_processed(self, db_engine_fk):
        """End-to-end: collect_source extracts items, process_items creates events."""
        session_factory = create_session_factory(db_engine_fk)

        # Seed database
        async with session_factory() as session:
            source, page = await _seed_source(session)
            source_id = source.id
            page_id = page.id
            await session.commit()

        # Build the scheduler with a real session factory but mocked externals
        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()  # Not used because collect_page is mocked

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

        fake_diff = DiffResult(changed=True, added_lines=["new content"], change_ratio=0.5)

        # Build a mock collector
        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.collect_page = AsyncMock(return_value=(fake_items, fake_diff))

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
        ):
            await scheduler.collect_source("TestOrg")

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

            # Verify page metadata was updated (times_polled, last_polled_at)
            page_result = await session.execute(select(Page).where(Page.id == page_id))
            page_record = page_result.scalar_one()
            assert page_record.times_polled >= 1
            assert page_record.last_polled_at is not None

        # Verify health tracker recorded success
        assert not scheduler.health.is_circuit_open("TestOrg")
        status = scheduler.health.get_status("TestOrg")
        assert status["last_success_at"] is not None
        assert status["consecutive_failures"] == 0

    async def test_collection_with_no_changes(self, db_engine_fk):
        """When the collector returns no items, no events are created."""
        session_factory = create_session_factory(db_engine_fk)

        async with session_factory() as session:
            await _seed_source(session)
            await session.commit()

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        source_config = _make_source_config("TestOrg")

        # Collector returns empty list (no changes detected)
        no_change_diff = DiffResult(changed=False)
        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.collect_page = AsyncMock(return_value=([], no_change_diff))

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.process_items",
                new_callable=AsyncMock,
            ) as mock_process,
        ):
            await scheduler.collect_source("TestOrg")

            # process_items should NOT have been called since all_items is empty
            mock_process.assert_not_called()

        # Verify no events in the database
        async with session_factory() as session:
            result = await session.execute(select(EventRecord))
            events = list(result.scalars().all())
            assert len(events) == 0

        # Health tracker should still record success (no-change is not a failure)
        status = scheduler.health.get_status("TestOrg")
        assert status["last_success_at"] is not None
        assert status["consecutive_failures"] == 0

    async def test_source_not_found_graceful_handling(self, db_engine_fk):
        """When the source org is not in the catalog, collect_source exits gracefully."""
        session_factory = create_session_factory(db_engine_fk)

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        # Return a catalog that does NOT include the requested organization
        other_config = _make_source_config("OtherOrg")

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[other_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
            ) as mock_get_collector,
            patch(
                "ai_benchmark.scheduling.scheduler.process_items",
                new_callable=AsyncMock,
            ) as mock_process,
        ):
            # Request collection for a source not in the catalog
            await scheduler.collect_source("NonExistentOrg")

            # Collector should never be instantiated
            mock_get_collector.assert_not_called()
            # Pipeline should never run
            mock_process.assert_not_called()

        # Health tracker should NOT have recorded success or failure
        # (the method returns early before the try/except success path)
        status = scheduler.health.get_status("NonExistentOrg")
        assert status["consecutive_failures"] == 0

    async def test_collector_page_error_continues_other_pages(self, db_engine_fk):
        """When one page raises an exception, other pages are still collected."""
        session_factory = create_session_factory(db_engine_fk)

        async with session_factory() as session:
            source = Source(
                source_name="MultiPage Source",
                category="vendor",
                organization="MultiPageOrg",
                homepage_url="https://multipage.example.com",
                base_domain="multipage.example.com",
                trust_rating=5.0,
                source_role="official announcements",
                classification="primary",
                collection_method="html",
            )
            session.add(source)
            await session.flush()

            page1 = Page(
                source_id=source.id,
                canonical_url="https://multipage.example.com/page1",
                page_type="model_catalog",
            )
            page2 = Page(
                source_id=source.id,
                canonical_url="https://multipage.example.com/page2",
                page_type="changelog",
            )
            session.add_all([page1, page2])
            await session.flush()
            await session.commit()

        source_config = SourceConfig(
            source_name="MultiPage Source",
            category="vendor",
            organization="MultiPageOrg",
            homepage_url="https://multipage.example.com",
            base_domain="multipage.example.com",
            trust_rating=5.0,
            source_role="official announcements",
            classification="primary",
            collection_method="html",
            pages=[
                PageConfig(
                    canonical_url="https://multipage.example.com/page1",
                    page_type="model_catalog",
                ),
                PageConfig(
                    canonical_url="https://multipage.example.com/page2",
                    page_type="changelog",
                ),
            ],
        )

        good_items = [
            RawItem(
                title="MultiPageOrg Releases NewModel",
                url="https://multipage.example.com/page2/new",
                body="NewModel is here",
                item_type="model_release",
                model_hint="newmodel",
            ),
        ]
        good_diff = DiffResult(changed=True, added_lines=["new"], change_ratio=0.3)

        # First page raises, second page succeeds
        async def mock_collect_page(page, fetcher, snapshot_mgr, page_id):
            if page.canonical_url.endswith("/page1"):
                raise ConnectionError("Simulated network failure")
            return good_items, good_diff

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.collect_page = AsyncMock(side_effect=mock_collect_page)

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
        ):
            await scheduler.collect_source("MultiPageOrg")

        # The event from page2 should still have been created
        async with session_factory() as session:
            result = await session.execute(select(EventRecord))
            events = list(result.scalars().all())
            assert len(events) == 1
            assert events[0].model_slug == "newmodel"

        # Overall collection is a success (partial page failure is tolerated)
        status = scheduler.health.get_status("MultiPageOrg")
        assert status["last_success_at"] is not None
        assert status["consecutive_failures"] == 0

    async def test_snapshot_created_during_collection(self, db_engine_fk):
        """Verify that snapshot records are created when the collector stores them."""
        session_factory = create_session_factory(db_engine_fk)

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
        fake_diff = DiffResult(changed=True, added_lines=["alpha"], change_ratio=0.4)

        # Instead of mocking collect_page entirely, mock the fetcher result
        # and let the real collect_page -> snapshot_mgr path run.
        # However, collect_page calls fetcher.fetch and snapshot_mgr.compare_with_latest,
        # so we mock collect_page but also separately store a snapshot to prove the flow.
        async def mock_collect_page_with_snapshot(page_cfg, fetcher, snapshot_mgr, page_id):
            # Simulate what a real collector does: store a snapshot, then return items
            await snapshot_mgr.store_snapshot(page_id, "<html>Model Alpha</html>")
            return fake_items, fake_diff

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = source_config.pages
        mock_collector.collect_page = AsyncMock(side_effect=mock_collect_page_with_snapshot)

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
        ):
            await scheduler.collect_source("TestOrg")

        # Verify snapshot was stored
        async with session_factory() as session:
            snap_result = await session.execute(select(Snapshot).where(Snapshot.page_id == page_id))
            snapshots = list(snap_result.scalars().all())
            assert len(snapshots) == 1
            assert "Model Alpha" in snapshots[0].content

            # Event should also exist
            event_result = await session.execute(select(EventRecord))
            events = list(event_result.scalars().all())
            assert len(events) == 1
            assert events[0].model_slug == "model-alpha"
