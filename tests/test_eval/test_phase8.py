"""Phase 8 tests — result capture, traces, artifacts, rescoring."""

from __future__ import annotations

import json
import os
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from ai_benchmark.eval.models.artifact import Artifact
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunItemResult
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.eval.models.trace import TraceReference
from ai_benchmark.eval.services import report_service
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


async def _create_run_fixture(session: AsyncSession) -> tuple[Run, list[TestCase]]:
    """Create a full FK chain and return (run, test_cases)."""
    ds = Dataset(name="p8-ds", source="manual")
    session.add(ds)
    await session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
    session.add(dv)
    await session.flush()

    tc1 = TestCase(
        dataset_version_id=dv.id, item_index=0, input_text="Q1", expected_output="correct"
    )
    tc2 = TestCase(dataset_version_id=dv.id, item_index=1, input_text="Q2", expected_output="right")
    session.add_all([tc1, tc2])
    await session.flush()

    scorer_obj = Scorer(name="p8-exact", scorer_type="exact_match")
    session.add(scorer_obj)
    await session.flush()

    sv = ScorerVersion(
        scorer_id=scorer_obj.id,
        version_number=1,
        config=json.dumps({"case_sensitive": False}),
    )
    session.add(sv)
    await session.flush()

    ed = EvaluationDefinition(name="p8-eval", execution_mode="sequential")
    session.add(ed)
    await session.flush()

    ev = EvaluationVersion(
        evaluation_id=ed.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps(
            [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5}]
        ),
    )
    session.add(ev)
    await session.flush()

    target = TargetConfiguration(
        name="p8-target", model_name="test-model", provider="openai", inference_params="{}"
    )
    session.add(target)
    await session.flush()

    run = Run(
        evaluation_version_id=ev.id,
        target_config_id=target.id,
        dataset_version_id=dv.id,
        status="running",
        total_items=2,
    )
    session.add(run)
    await session.flush()

    return run, [tc1, tc2]


# ── Trace Capture ──


class TestTraceCapture:
    @pytest.mark.asyncio
    async def test_executor_creates_traces(self, db_session):
        """Verify ItemExecutor stores TraceReference rows after execution."""
        from sqlalchemy import select

        from ai_benchmark.eval.execution.adapters.base import GenerationResult
        from ai_benchmark.eval.execution.executor import ItemExecutor

        run, test_cases = await _create_run_fixture(db_session)

        mock_result = GenerationResult(
            output_text="correct",
            latency_ms=150.0,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_estimate_usd=0.001,
        )

        executor = ItemExecutor(
            provider="openai", model_name="test-model", endpoint_url="http://localhost"
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            item_result = await executor.execute_item(db_session, run.id, test_cases[0], 0)

        # Verify traces were created
        stmt = select(TraceReference).where(TraceReference.run_item_result_id == item_result.id)
        result = await db_session.execute(stmt)
        traces = list(result.scalars().all())

        trace_types = {t.trace_type for t in traces}
        assert "token_usage" in trace_types
        assert "latency_breakdown" in trace_types
        assert "cost_estimate" in trace_types

        # Verify token usage data
        token_trace = next(t for t in traces if t.trace_type == "token_usage")
        data = json.loads(token_trace.trace_data)
        assert data["prompt_tokens"] == 10
        assert data["completion_tokens"] == 5
        assert data["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_retry_log_trace(self, db_session):
        """Verify retry log trace is created when retries occur."""
        from sqlalchemy import select

        from ai_benchmark.eval.execution.adapters.base import GenerationResult
        from ai_benchmark.eval.execution.executor import ItemExecutor

        run, test_cases = await _create_run_fixture(db_session)

        # First call fails, second succeeds
        fail_result = GenerationResult(output_text="", error="Timeout")
        ok_result = GenerationResult(output_text="correct", latency_ms=100.0)

        executor = ItemExecutor(
            provider="openai",
            model_name="test-model",
            max_retries=2,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.side_effect = [fail_result, ok_result]
            mock_resolve.return_value = mock_adapter

            item_result = await executor.execute_item(db_session, run.id, test_cases[0], 0)

        stmt = select(TraceReference).where(
            TraceReference.run_item_result_id == item_result.id,
            TraceReference.trace_type == "retry_log",
        )
        result = await db_session.execute(stmt)
        retry_trace = result.scalar_one_or_none()
        assert retry_trace is not None
        data = json.loads(retry_trace.trace_data)
        assert data["attempts"] == 2
        assert len(data["log"]) == 1
        assert data["log"][0]["error"] == "Timeout"

    @pytest.mark.asyncio
    async def test_normalized_output_stored(self, db_session):
        """Verify normalized_output is populated as stripped raw_output."""
        from ai_benchmark.eval.execution.adapters.base import GenerationResult
        from ai_benchmark.eval.execution.executor import ItemExecutor

        run, test_cases = await _create_run_fixture(db_session)

        mock_result = GenerationResult(output_text="  hello world  \n", latency_ms=50.0)

        executor = ItemExecutor(provider="openai", model_name="test-model")

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            item_result = await executor.execute_item(db_session, run.id, test_cases[0], 0)

        assert item_result.raw_output == "  hello world  \n"
        assert item_result.normalized_output == "hello world"


# ── Export Formats ──


class TestExportFormats:
    def test_export_markdown_basic(self):
        data = {
            "run_id": 1,
            "status": "completed",
            "total_items": 2,
            "completed_items": 2,
            "failed_items": 0,
            "model_name": "gpt-4",
            "provider": "openai",
            "metrics": {"pass_rate": 0.75, "avg_latency_ms": 120.5},
            "items": [
                {"index": 0, "pass": True, "latency_ms": 100, "tokens": 50, "error": None},
                {"index": 1, "pass": False, "latency_ms": 141, "tokens": 60, "error": None},
            ],
        }
        md = report_service.export_markdown(data, title="Test Report")
        assert "# Test Report" in md
        assert "**Run ID**: 1" in md
        assert "pass_rate" in md
        assert "| 0 | PASS |" in md
        assert "| 1 | FAIL |" in md

    def test_export_markdown_grouped(self):
        data = {
            "groups": {
                "group_a": [{"run_id": 1, "model_name": "gpt-4", "metrics": {"pass_rate": 0.9}}]
            }
        }
        md = report_service.export_markdown(data)
        assert "### group_a" in md
        assert "Run 1" in md

    def test_export_html_escapes_xss(self):
        """Verify HTML export escapes user-controlled data."""
        data = {
            "groups": {
                '<script>alert("xss")</script>': [
                    {
                        "run_id": 1,
                        "model_name": '<img onerror="alert(1)">',
                        "metrics": {},
                    }
                ]
            }
        }
        html_out = report_service.export_html(data, title="<script>bad</script>")
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out

    def test_export_html_single_run(self):
        data = {
            "run_id": 1,
            "status": "completed",
            "model_name": "gpt-4",
            "metrics": {"pass_rate": 0.8},
            "items": [
                {"index": 0, "pass": True, "latency_ms": 100, "error": None},
            ],
        }
        html_out = report_service.export_html(data, title="Run 1")
        assert "<h2>Metrics</h2>" in html_out
        assert "pass_rate" in html_out
        assert "PASS" in html_out


# ── Artifact Service ──


class TestArtifactService:
    @pytest.mark.asyncio
    async def test_generate_run_artifacts(self, db_session):
        """Test artifact generation for all formats."""
        from ai_benchmark.eval.config import EvalSettings
        from ai_benchmark.eval.services import artifact_service

        run, _ = await _create_run_fixture(db_session)

        # Add item results
        item = RunItemResult(
            run_id=run.id,
            test_case_id=1,
            item_index=0,
            input_sent="Q1",
            raw_output="correct",
            normalized_output="correct",
            scorer_results="[]",
            overall_pass=True,
            latency_ms=100.0,
            total_tokens=10,
        )
        db_session.add(item)

        metric = RunAggregateMetric(run_id=run.id, metric_name="pass_rate", metric_value=1.0)
        db_session.add(metric)
        await db_session.flush()

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = EvalSettings(artifact_storage_path=tmpdir)
            artifacts = await artifact_service.generate_run_artifacts(
                db_session, run.id, settings=settings
            )

        assert len(artifacts) == 4  # json, csv, markdown, html
        types = {a.artifact_type for a in artifacts}
        assert types == {"export_json", "export_csv", "export_markdown", "export_html"}
        assert all(a.size_bytes > 0 for a in artifacts)

    @pytest.mark.asyncio
    async def test_store_execution_log(self, db_session):
        from ai_benchmark.eval.config import EvalSettings
        from ai_benchmark.eval.services import artifact_service

        run, _ = await _create_run_fixture(db_session)

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = EvalSettings(artifact_storage_path=tmpdir)
            artifact = await artifact_service.store_execution_log(
                db_session,
                run.id,
                "2026-03-28 10:00 Starting run\n2026-03-28 10:01 Completed",
                settings=settings,
            )

        assert artifact.artifact_type == "execution_log"
        assert artifact.mime_type == "text/plain"
        assert artifact.size_bytes > 0

    @pytest.mark.asyncio
    async def test_cleanup_artifacts(self, db_session):
        """Test retention policy enforcement."""
        from datetime import UTC, datetime, timedelta

        from ai_benchmark.eval.config import EvalSettings
        from ai_benchmark.eval.services import artifact_service

        run, _ = await _create_run_fixture(db_session)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an artifact file
            file_path = os.path.join(tmpdir, "old_artifact.json")
            with open(file_path, "w") as f:
                f.write("{}")

            old_artifact = Artifact(
                run_id=run.id,
                artifact_type="export_json",
                filename="old_artifact.json",
                file_path=file_path,
                size_bytes=2,
                mime_type="application/json",
            )
            db_session.add(old_artifact)
            await db_session.flush()

            # Manually backdate the artifact
            old_artifact.created_at = datetime.now(UTC) - timedelta(days=100)
            await db_session.flush()

            settings = EvalSettings(artifact_storage_path=tmpdir)
            removed = await artifact_service.cleanup_artifacts(
                db_session, max_age_days=90, settings=settings
            )

            assert removed >= 1
            assert not os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_comparison_bundle(self, db_session):
        """Test comparison bundle generation for multiple runs."""
        from ai_benchmark.eval.config import EvalSettings
        from ai_benchmark.eval.services import artifact_service

        run1, _ = await _create_run_fixture(db_session)

        # Create a second run
        run2 = Run(
            evaluation_version_id=run1.evaluation_version_id,
            target_config_id=run1.target_config_id,
            dataset_version_id=run1.dataset_version_id,
            status="completed",
            total_items=2,
        )
        db_session.add(run2)
        await db_session.flush()

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = EvalSettings(artifact_storage_path=tmpdir)
            artifact = await artifact_service.generate_comparison_bundle(
                db_session, [run1.id, run2.id], settings=settings
            )

        assert artifact is not None
        assert artifact.artifact_type == "comparison_bundle"
        assert artifact.mime_type == "application/json"


# ── Rescoring ──


class TestRescoring:
    @pytest.mark.asyncio
    async def test_rescore_run(self, db_session):
        """Test rescoring a run with a new scorer config."""
        from ai_benchmark.eval.services import run_service

        run, test_cases = await _create_run_fixture(db_session)

        # Add item results as if execution completed
        item1 = RunItemResult(
            run_id=run.id,
            test_case_id=test_cases[0].id,
            item_index=0,
            input_sent="Q1",
            raw_output="correct",
            scorer_results="[]",
            overall_pass=None,
            latency_ms=50,
        )
        item2 = RunItemResult(
            run_id=run.id,
            test_case_id=test_cases[1].id,
            item_index=1,
            input_sent="Q2",
            raw_output="wrong",
            scorer_results="[]",
            overall_pass=None,
            latency_ms=75,
        )
        db_session.add_all([item1, item2])
        await db_session.flush()

        # Get the scorer version ID
        from sqlalchemy import select

        from ai_benchmark.eval.models.scorer import ScorerVersion

        sv_stmt = select(ScorerVersion).limit(1)
        sv_result = await db_session.execute(sv_stmt)
        sv = sv_result.scalar_one()

        # Rescore
        new_config = [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5}]
        rescored_run = await run_service.rescore_run(db_session, run.id, new_config)

        assert rescored_run is not None
        assert rescored_run.status in ("completed", "partially_completed", "failed")

        # Verify item results were updated
        await db_session.refresh(item1)
        await db_session.refresh(item2)
        assert item1.overall_pass is True  # "correct" matches expected
        assert item2.overall_pass is False  # "wrong" doesn't match

        # Verify aggregates computed
        metrics = await run_service.get_metrics(db_session, run.id)
        metric_names = {m.metric_name for m in metrics}
        assert "pass_rate" in metric_names

    @pytest.mark.asyncio
    async def test_rescore_updates_aggregates(self, db_session):
        """Verify re-aggregation overwrites old metrics via upsert."""
        from ai_benchmark.eval.services import run_service

        run, test_cases = await _create_run_fixture(db_session)

        item = RunItemResult(
            run_id=run.id,
            test_case_id=test_cases[0].id,
            item_index=0,
            input_sent="Q1",
            raw_output="correct",
            scorer_results="[]",
            latency_ms=100,
            total_tokens=20,
        )
        db_session.add(item)
        await db_session.flush()

        # First score
        from sqlalchemy import select

        from ai_benchmark.eval.models.scorer import ScorerVersion

        sv_stmt = select(ScorerVersion).limit(1)
        sv_result = await db_session.execute(sv_stmt)
        sv = sv_result.scalar_one()

        config = [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5}]
        await run_service.rescore_run(db_session, run.id, config)

        metrics1 = await run_service.get_metrics(db_session, run.id)
        pass_rate_1 = next(m.metric_value for m in metrics1 if m.metric_name == "pass_rate")
        assert pass_rate_1 == 1.0  # "correct" matches

        # Rescore with higher threshold — still passes (exact match = 1.0)
        config2 = [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.9}]
        await run_service.rescore_run(db_session, run.id, config2)

        metrics2 = await run_service.get_metrics(db_session, run.id)
        pass_rate_2 = next(m.metric_value for m in metrics2 if m.metric_name == "pass_rate")
        assert pass_rate_2 == 1.0  # Still passes (score=1.0 >= 0.9)


# ── Trace Retrieval ──


class TestTraceRetrieval:
    @pytest.mark.asyncio
    async def test_get_traces(self, db_session):
        """Test fetching traces for an item result."""
        from ai_benchmark.eval.services import run_service

        run, test_cases = await _create_run_fixture(db_session)

        item = RunItemResult(
            run_id=run.id,
            test_case_id=test_cases[0].id,
            item_index=0,
            input_sent="Q1",
            raw_output="answer",
            scorer_results="[]",
        )
        db_session.add(item)
        await db_session.flush()

        trace = TraceReference(
            run_item_result_id=item.id,
            trace_type="token_usage",
            trace_data=json.dumps(
                {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            ),
        )
        db_session.add(trace)
        await db_session.flush()

        traces = await run_service.get_traces(db_session, item.id)
        assert len(traces) == 1
        assert traces[0].trace_type == "token_usage"
