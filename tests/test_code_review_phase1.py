"""Phase 1 code review remediation tests.

Tests for findings F-01/F-02 (scheduler), F-05 (race condition),
F-07 (XSS in export_html), and F-08 (API key redaction).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.models.base import create_session_factory
from ai_benchmark.models.sources import Page, Source

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def api_client(db_engine_fk):
    import ai_benchmark.eval.api.app as app_module

    settings = EvalSettings()
    app = create_app(settings)

    test_factory = create_session_factory(db_engine_fk)
    original = app_module._session_factory
    app_module._session_factory = test_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        yield client

    app_module._session_factory = original


# ─── F-01/F-02: Scheduler collect_source ───


class TestSchedulerCollectSource:
    """Integration tests for the fixed collect_source method."""

    @pytest.mark.asyncio
    async def test_collect_source_creates_page_records(self, db_engine_fk):
        """Verify collect_source looks up/creates Page records with real IDs."""
        session_factory = create_session_factory(db_engine_fk)

        # Create a source record
        async with session_factory() as session:
            source = Source(
                source_name="Test Source",
                category="primary",
                organization="TestOrg",
                homepage_url="https://test.example.com",
                base_domain="test.example.com",
                trust_rating=5.0,
                source_role="vendor",
                classification="primary",
            )
            session.add(source)
            await session.commit()

        from ai_benchmark.config.settings import PageConfig, PipelineSettings, SourceConfig

        mock_source_config = SourceConfig(
            source_name="Test Source",
            category="primary",
            organization="TestOrg",
            homepage_url="https://test.example.com",
            base_domain="test.example.com",
            trust_rating=5.0,
            source_role="vendor",
            classification="primary",
            pages=[
                PageConfig(
                    canonical_url="https://test.example.com/models",
                    page_type="model_catalog",
                ),
            ],
        )

        # Mock the collector
        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = mock_source_config.pages
        mock_collector.collect_page = AsyncMock(return_value=([], None))

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")

        from ai_benchmark.scheduling.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[mock_source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
        ):
            await scheduler.collect_source("TestOrg")

        # Verify the page was created in the DB
        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Page).where(Page.canonical_url == "https://test.example.com/models")
            )
            page = result.scalar_one_or_none()
            assert page is not None, "Page record should have been created"
            assert page.page_type == "model_catalog"
            assert page.id > 0, "Page should have a real database ID"

    @pytest.mark.asyncio
    async def test_collect_source_passes_session_to_snapshot_manager(self, db_engine_fk):
        """Verify SnapshotManager receives an AsyncSession, not a factory."""
        session_factory = create_session_factory(db_engine_fk)

        # Create a source record
        async with session_factory() as session:
            source = Source(
                source_name="Test Source 2",
                category="primary",
                organization="TestOrg2",
                homepage_url="https://test2.example.com",
                base_domain="test2.example.com",
                trust_rating=5.0,
                source_role="vendor",
                classification="primary",
            )
            session.add(source)
            await session.commit()

        from ai_benchmark.config.settings import PageConfig, PipelineSettings, SourceConfig

        mock_source_config = SourceConfig(
            source_name="Test Source 2",
            category="primary",
            organization="TestOrg2",
            homepage_url="https://test2.example.com",
            base_domain="test2.example.com",
            trust_rating=5.0,
            source_role="vendor",
            classification="primary",
            pages=[
                PageConfig(
                    canonical_url="https://test2.example.com/models",
                    page_type="model_catalog",
                ),
            ],
        )

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = mock_source_config.pages
        mock_collector.collect_page = AsyncMock(return_value=([], None))

        captured_snapshot_mgr = {}

        original_init = None

        def capture_snapshot_mgr(self_inner, session):
            from sqlalchemy.ext.asyncio import AsyncSession

            assert isinstance(session, AsyncSession), f"Expected AsyncSession, got {type(session)}"
            captured_snapshot_mgr["session"] = session
            original_init(self_inner, session)

        from ai_benchmark.collection.snapshot import SnapshotManager

        original_init = SnapshotManager.__init__

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")

        from ai_benchmark.scheduling.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[mock_source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
            patch.object(SnapshotManager, "__init__", capture_snapshot_mgr),
        ):
            await scheduler.collect_source("TestOrg2")

        assert "session" in captured_snapshot_mgr, "SnapshotManager should have been created"

    @pytest.mark.asyncio
    async def test_collect_source_updates_page_metadata(self, db_engine_fk):
        """Verify page metadata (times_polled, last_polled_at) is updated after collection."""
        session_factory = create_session_factory(db_engine_fk)

        async with session_factory() as session:
            source = Source(
                source_name="Test Source 3",
                category="primary",
                organization="TestOrg3",
                homepage_url="https://test3.example.com",
                base_domain="test3.example.com",
                trust_rating=5.0,
                source_role="vendor",
                classification="primary",
            )
            session.add(source)
            await session.flush()

            page = Page(
                source_id=source.id,
                canonical_url="https://test3.example.com/pricing",
                page_type="pricing",
                times_polled=0,
            )
            session.add(page)
            await session.commit()

        from ai_benchmark.config.settings import PageConfig, PipelineSettings, SourceConfig

        mock_source_config = SourceConfig(
            source_name="Test Source 3",
            category="primary",
            organization="TestOrg3",
            homepage_url="https://test3.example.com",
            base_domain="test3.example.com",
            trust_rating=5.0,
            source_role="vendor",
            classification="primary",
            pages=[
                PageConfig(
                    canonical_url="https://test3.example.com/pricing",
                    page_type="pricing",
                ),
            ],
        )

        mock_collector = MagicMock()
        mock_collector.get_pages.return_value = mock_source_config.pages
        mock_collector.collect_page = AsyncMock(return_value=([], None))

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")

        from ai_benchmark.scheduling.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        with (
            patch(
                "ai_benchmark.scheduling.scheduler.load_source_catalog",
                return_value=[mock_source_config],
            ),
            patch(
                "ai_benchmark.scheduling.scheduler.get_collector",
                return_value=mock_collector,
            ),
        ):
            await scheduler.collect_source("TestOrg3")

        # Verify page metadata was updated
        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Page).where(Page.canonical_url == "https://test3.example.com/pricing")
            )
            page = result.scalar_one()
            assert page.times_polled >= 1, "times_polled should have been incremented"
            assert page.last_polled_at is not None, "last_polled_at should be set"

    @pytest.mark.asyncio
    async def test_collect_source_circuit_open_skips(self, db_engine_fk):
        """Verify collect_source skips when circuit breaker is open."""
        session_factory = create_session_factory(db_engine_fk)

        from ai_benchmark.config.settings import PipelineSettings
        from ai_benchmark.scheduling.scheduler import MAX_CONSECUTIVE_FAILURES, PipelineScheduler

        settings = PipelineSettings(database_url="sqlite+aiosqlite:///:memory:")
        scheduler = PipelineScheduler(settings)
        scheduler._session_factory = session_factory
        scheduler._fetcher = MagicMock()

        # Trip the circuit breaker
        for i in range(MAX_CONSECUTIVE_FAILURES):
            scheduler.health.record_failure("BrokenOrg", f"Error {i}")

        with patch("ai_benchmark.scheduling.scheduler.load_source_catalog") as mock_catalog:
            await scheduler.collect_source("BrokenOrg")
            mock_catalog.assert_not_called()


# ─── F-05: Parallel execution race condition ───


class TestParallelExecutionRaceCondition:
    """Tests that parallel execution correctly counts completed/failed items."""

    @pytest.mark.asyncio
    async def test_parallel_counter_accuracy(self, db_session):
        """Run parallel execution with 20 items and verify counts are accurate."""
        # Create minimal test data
        ds = Dataset(name="race_test_ds")
        db_session.add(ds)
        await db_session.flush()

        dsv = DatasetVersion(dataset_id=ds.id, version_number=1)
        db_session.add(dsv)
        await db_session.flush()

        test_cases = []
        for i in range(20):
            tc = TestCase(
                dataset_version_id=dsv.id,
                item_index=i,
                input_text=f"Input {i}",
                expected_output=f"Output {i}",
            )
            db_session.add(tc)
            test_cases.append(tc)
        await db_session.flush()

        ed = EvaluationDefinition(name="race_test_eval")
        db_session.add(ed)
        await db_session.flush()

        ev = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dsv.id,
            scorer_config="[]",
        )
        db_session.add(ev)
        await db_session.flush()

        tc_config = TargetConfiguration(
            name="race_test_target",
            model_name="test-model",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(tc_config)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=tc_config.id,
            dataset_version_id=dsv.id,
            status="running",
            total_items=20,
            completed_items=0,
            failed_items=0,
        )
        db_session.add(run)
        await db_session.flush()

        # Create a mock executor that alternates success/failure
        mock_executor = MagicMock()

        async def mock_execute_item(session, run_id, test_case, idx):
            # Add tiny delay to increase chance of race conditions
            await asyncio.sleep(0.001)
            result = MagicMock()
            # Even items succeed, odd items fail
            result.error_message = "Simulated failure" if idx % 2 == 1 else None
            return result

        mock_executor.execute_item = mock_execute_item

        from ai_benchmark.eval.execution.orchestrator import RunOrchestrator

        orchestrator = RunOrchestrator()
        await orchestrator._execute_parallel(db_session, run, mock_executor, test_cases)

        # 10 even items succeed, 10 odd items fail
        assert run.completed_items == 10, f"Expected 10 completed, got {run.completed_items}"
        assert run.failed_items == 10, f"Expected 10 failed, got {run.failed_items}"

    @pytest.mark.asyncio
    async def test_parallel_all_success(self, db_session):
        """All items succeed in parallel — verify total count."""
        ds = Dataset(name="parallel_ok_ds")
        db_session.add(ds)
        await db_session.flush()

        dsv = DatasetVersion(dataset_id=ds.id, version_number=1)
        db_session.add(dsv)
        await db_session.flush()

        test_cases = []
        for i in range(15):
            tc = TestCase(
                dataset_version_id=dsv.id,
                item_index=i,
                input_text=f"Input {i}",
            )
            db_session.add(tc)
            test_cases.append(tc)
        await db_session.flush()

        ed = EvaluationDefinition(name="parallel_ok_eval")
        db_session.add(ed)
        await db_session.flush()

        ev = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dsv.id,
            scorer_config="[]",
        )
        db_session.add(ev)
        await db_session.flush()

        tc_config = TargetConfiguration(
            name="parallel_ok_target",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(tc_config)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=tc_config.id,
            dataset_version_id=dsv.id,
            status="running",
            total_items=15,
            completed_items=0,
            failed_items=0,
        )
        db_session.add(run)
        await db_session.flush()

        mock_executor = MagicMock()

        async def mock_execute_item(session, run_id, test_case, idx):
            await asyncio.sleep(0.001)
            result = MagicMock()
            result.error_message = None
            return result

        mock_executor.execute_item = mock_execute_item

        from ai_benchmark.eval.execution.orchestrator import RunOrchestrator

        orchestrator = RunOrchestrator()
        await orchestrator._execute_parallel(db_session, run, mock_executor, test_cases)

        assert run.completed_items == 15
        assert run.failed_items == 0

    @pytest.mark.asyncio
    async def test_parallel_all_exceptions(self, db_session):
        """All items raise exceptions — verify failed count."""
        ds = Dataset(name="parallel_fail_ds")
        db_session.add(ds)
        await db_session.flush()

        dsv = DatasetVersion(dataset_id=ds.id, version_number=1)
        db_session.add(dsv)
        await db_session.flush()

        test_cases = []
        for i in range(10):
            tc = TestCase(dataset_version_id=dsv.id, item_index=i, input_text=f"In {i}")
            db_session.add(tc)
            test_cases.append(tc)
        await db_session.flush()

        ed = EvaluationDefinition(name="parallel_fail_eval")
        db_session.add(ed)
        await db_session.flush()

        ev = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dsv.id,
            scorer_config="[]",
        )
        db_session.add(ev)
        await db_session.flush()

        tc_config = TargetConfiguration(
            name="parallel_fail_target",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(tc_config)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=tc_config.id,
            dataset_version_id=dsv.id,
            status="running",
            total_items=10,
            completed_items=0,
            failed_items=0,
        )
        db_session.add(run)
        await db_session.flush()

        mock_executor = MagicMock()

        async def mock_execute_item(session, run_id, test_case, idx):
            raise RuntimeError("Boom")

        mock_executor.execute_item = mock_execute_item

        from ai_benchmark.eval.execution.orchestrator import RunOrchestrator

        orchestrator = RunOrchestrator()
        await orchestrator._execute_parallel(db_session, run, mock_executor, test_cases)

        assert run.completed_items == 0
        assert run.failed_items == 10


# ─── F-07: XSS in export_html ───


class TestExportHtmlXSS:
    """Verify export_html escapes user-controlled data."""

    def test_xss_in_title(self):
        from ai_benchmark.eval.services.report_service import export_html

        data = {"run_id": 1, "status": "completed"}
        html = export_html(data, title='<script>alert("xss")</script>')
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_xss_in_group_name(self):
        from ai_benchmark.eval.services.report_service import export_html

        data = {
            "groups": {
                '<img src=x onerror="alert(1)">': [
                    {"run_id": 1, "model_name": "safe", "metrics": {"acc": 0.9}},
                ],
            }
        }
        html = export_html(data)
        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html

    def test_xss_in_model_name(self):
        from ai_benchmark.eval.services.report_service import export_html

        data = {
            "groups": {
                "safe_group": [
                    {
                        "run_id": 1,
                        "model_name": "<script>steal()</script>",
                        "metrics": {"acc": 0.5},
                    },
                ],
            }
        }
        html = export_html(data)
        assert "<script>steal()</script>" not in html

    def test_xss_in_run_status(self):
        from ai_benchmark.eval.services.report_service import export_html

        data = {"run_id": 1, "status": '<b onmouseover="hack()">done</b>'}
        html = export_html(data)
        assert 'onmouseover="hack()"' not in html

    def test_xss_in_item_error(self):
        from ai_benchmark.eval.services.report_service import export_html

        data = {
            "run_id": 1,
            "items": [
                {
                    "index": 0,
                    "input": "test",
                    "output": "ok",
                    "error": "<script>xss</script>",
                    "pass": True,
                }
            ],
        }
        html = export_html(data)
        assert "<script>xss</script>" not in html


# ─── F-08: API key redaction ───


class TestApiKeyRedaction:
    """Verify API keys are redacted from target config API responses."""

    @pytest.mark.asyncio
    async def test_get_target_redacts_api_key(self, db_session, api_client):
        """GET a target with api_key in runtime_options — verify it's redacted."""
        tc = TargetConfiguration(
            name="key_test_target",
            model_name="gpt-4",
            provider="openai",
            inference_params="{}",
            runtime_options=json.dumps(
                {
                    "api_key": "sk-secret-12345",
                    "timeout": 30,
                }
            ),
        )
        db_session.add(tc)
        await db_session.commit()

        resp = await api_client.get(f"/api/eval/targets/{tc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runtime_options"]["api_key"] == "***REDACTED***"
        assert data["runtime_options"]["timeout"] == 30

    @pytest.mark.asyncio
    async def test_list_targets_redacts_api_key(self, db_session, api_client):
        """GET targets list — verify api_key is redacted."""
        tc = TargetConfiguration(
            name="list_key_target",
            model_name="claude-3",
            provider="anthropic",
            inference_params="{}",
            runtime_options=json.dumps(
                {
                    "api_key": "sk-ant-secret",
                    "secret_key": "super-secret",
                    "max_tokens": 1000,
                }
            ),
        )
        db_session.add(tc)
        await db_session.commit()

        resp = await api_client.get("/api/eval/targets")
        assert resp.status_code == 200
        targets = resp.json()
        matching = [t for t in targets if t["name"] == "list_key_target"]
        assert len(matching) == 1
        opts = matching[0]["runtime_options"]
        assert opts["api_key"] == "***REDACTED***"
        assert opts["secret_key"] == "***REDACTED***"
        assert opts["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_target_without_runtime_options(self, db_session, api_client):
        """GET a target with no runtime_options — verify no crash."""
        tc = TargetConfiguration(
            name="no_opts_target",
            model_name="gpt-4",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(tc)
        await db_session.commit()

        resp = await api_client.get(f"/api/eval/targets/{tc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runtime_options"] is None

    @pytest.mark.asyncio
    async def test_redact_keys_function(self):
        """Direct unit test for _redact_keys."""
        from ai_benchmark.eval.api.serializers import _redact_keys

        result = _redact_keys(
            {
                "api_key": "secret",
                "token": "tok123",
                "password": "pass",
                "timeout": 30,
                "model": "gpt-4",
            }
        )
        assert result["api_key"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["timeout"] == 30
        assert result["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_redact_keys_none_input(self):
        """_redact_keys handles None input."""
        from ai_benchmark.eval.api.serializers import _redact_keys

        assert _redact_keys(None) is None
