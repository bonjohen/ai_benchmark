"""Tests for ItemExecutor — adapter resolution, prompt building, retry behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_benchmark.eval.execution.adapters.base import (
    _ADAPTER_REGISTRY,
    GenerationResult,
    resolve_adapter,
)
from ai_benchmark.eval.execution.executor import ItemExecutor
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401 — resolve mapper
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.models.base import create_session_factory

# ── Fixtures ──


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def dataset_chain(db_session):
    """Create dataset → version → test cases."""
    ds = Dataset(name="exec-ds", source="manual")
    db_session.add(ds)
    await db_session.flush()

    dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=3)
    db_session.add(dv)
    await db_session.flush()

    cases = []
    for i in range(3):
        tc = TestCase(
            dataset_version_id=dv.id,
            item_index=i,
            input_text=f"Question {i}",
            expected_output=f"Answer {i}",
            context=f"Context {i}",
        )
        db_session.add(tc)
        cases.append(tc)
    await db_session.flush()
    return ds, dv, cases


# ── Adapter Registry Tests ──


class TestAdapterRegistry:
    def test_resolve_known_adapters(self):
        """All four adapters are registered after import."""
        # Trigger registration
        from ai_benchmark.eval.execution.adapters import (  # noqa: F401
            anthropic_adapter,
            generic_http_adapter,
            local_adapter,
            openai_adapter,
        )

        assert "openai" in _ADAPTER_REGISTRY
        assert "anthropic" in _ADAPTER_REGISTRY
        assert "local_ollama" in _ADAPTER_REGISTRY
        assert "local_vllm" in _ADAPTER_REGISTRY
        assert "local_llamacpp" in _ADAPTER_REGISTRY
        assert "generic_http" in _ADAPTER_REGISTRY

    def test_resolve_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="No adapter registered"):
            resolve_adapter("nonexistent_provider")

    def test_resolve_openai_returns_correct_type(self):
        adapter = resolve_adapter("openai", api_key="test-key", model_name="gpt-4o")
        from ai_benchmark.eval.execution.adapters.openai_adapter import OpenAIAdapter

        assert isinstance(adapter, OpenAIAdapter)

    def test_resolve_anthropic_returns_correct_type(self):
        adapter = resolve_adapter("anthropic", api_key="test-key")
        from ai_benchmark.eval.execution.adapters.anthropic_adapter import AnthropicAdapter

        assert isinstance(adapter, AnthropicAdapter)


# ── Prompt Building Tests ──


class TestPromptBuilding:
    def test_plain_input(self):
        executor = ItemExecutor(provider="openai")
        tc = TestCase(dataset_version_id=1, item_index=0, input_text="Hello world")
        assert executor._build_prompt(tc) == "Hello world"

    def test_prompt_template_replaces_input(self):
        executor = ItemExecutor(
            provider="openai",
            prompt_template="Answer this: {{input}}",
        )
        tc = TestCase(dataset_version_id=1, item_index=0, input_text="What is 2+2?")
        assert executor._build_prompt(tc) == "Answer this: What is 2+2?"

    def test_prompt_template_replaces_context_and_expected(self):
        executor = ItemExecutor(
            provider="openai",
            prompt_template="Context: {{context}}\nQ: {{input}}\nExpected: {{expected}}",
        )
        tc = TestCase(
            dataset_version_id=1,
            item_index=0,
            input_text="Q1",
            context="Ctx1",
            expected_output="A1",
        )
        result = executor._build_prompt(tc)
        assert "Context: Ctx1" in result
        assert "Q: Q1" in result
        assert "Expected: A1" in result

    def test_prompt_wrapper_wraps_template(self):
        executor = ItemExecutor(
            provider="openai",
            prompt_template="Q: {{input}}",
            prompt_wrapper="[SYSTEM]\n{{prompt}}\n[/SYSTEM]",
        )
        tc = TestCase(dataset_version_id=1, item_index=0, input_text="Hi")
        result = executor._build_prompt(tc)
        assert result == "[SYSTEM]\nQ: Hi\n[/SYSTEM]"


# ── Item Execution Tests ──


class TestItemExecution:
    @pytest.mark.asyncio
    async def test_successful_execution(self, db_session, dataset_chain):
        """Mock adapter returns success → RunItemResult stored."""
        ds, dv, cases = dataset_chain

        mock_result = GenerationResult(
            output_text="Answer 0",
            latency_ms=42.5,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            # We need a valid run_id; create minimal FK chain
            from ai_benchmark.eval.models.evaluation import (
                EvaluationDefinition,
                EvaluationVersion,
            )
            from ai_benchmark.eval.models.run import Run
            from ai_benchmark.eval.models.target import TargetConfiguration

            ed = EvaluationDefinition(name="test-eval", execution_mode="sequential")
            db_session.add(ed)
            await db_session.flush()

            ev = EvaluationVersion(
                evaluation_id=ed.id,
                version_number=1,
                dataset_version_id=dv.id,
                scorer_config="[]",
            )
            db_session.add(ev)
            await db_session.flush()

            tc_target = TargetConfiguration(
                name="test-target",
                model_name="gpt-4o",
                provider="openai",
                inference_params="{}",
            )
            db_session.add(tc_target)
            await db_session.flush()

            run = Run(
                evaluation_version_id=ev.id,
                target_config_id=tc_target.id,
                dataset_version_id=dv.id,
                status="running",
                total_items=3,
            )
            db_session.add(run)
            await db_session.flush()

            executor = ItemExecutor(provider="openai", model_name="gpt-4o")
            item_result = await executor.execute_item(db_session, run.id, cases[0], 0)

            assert item_result.raw_output == "Answer 0"
            assert item_result.latency_ms == 42.5
            assert item_result.prompt_tokens == 10
            assert item_result.completion_tokens == 5
            assert item_result.error_message is None

    @pytest.mark.asyncio
    async def test_error_captured(self, db_session, dataset_chain):
        """Adapter returns error → stored in item_result.error_message."""
        ds, dv, cases = dataset_chain

        mock_result = GenerationResult(
            output_text="",
            latency_ms=100.0,
            error="HTTP 500: Internal Server Error",
        )

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            from ai_benchmark.eval.models.evaluation import (
                EvaluationDefinition,
                EvaluationVersion,
            )
            from ai_benchmark.eval.models.run import Run
            from ai_benchmark.eval.models.target import TargetConfiguration

            ed = EvaluationDefinition(name="err-eval", execution_mode="sequential")
            db_session.add(ed)
            await db_session.flush()

            ev = EvaluationVersion(
                evaluation_id=ed.id,
                version_number=1,
                dataset_version_id=dv.id,
                scorer_config="[]",
            )
            db_session.add(ev)
            await db_session.flush()

            tc_target = TargetConfiguration(
                name="err-target",
                model_name="gpt-4o",
                provider="openai",
                inference_params="{}",
            )
            db_session.add(tc_target)
            await db_session.flush()

            run = Run(
                evaluation_version_id=ev.id,
                target_config_id=tc_target.id,
                dataset_version_id=dv.id,
                status="running",
                total_items=1,
            )
            db_session.add(run)
            await db_session.flush()

            executor = ItemExecutor(provider="openai", max_retries=0)
            item_result = await executor.execute_item(db_session, run.id, cases[0], 0)

            assert item_result.error_message == "HTTP 500: Internal Server Error"
            assert item_result.raw_output == ""

    @pytest.mark.asyncio
    async def test_retry_on_error(self, db_session, dataset_chain):
        """Adapter fails then succeeds → retry_count recorded."""
        ds, dv, cases = dataset_chain

        fail_result = GenerationResult(output_text="", latency_ms=50.0, error="Timeout")
        success_result = GenerationResult(output_text="OK", latency_ms=80.0)

        with patch("ai_benchmark.eval.execution.executor.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.side_effect = [fail_result, success_result]
            mock_resolve.return_value = mock_adapter

            from ai_benchmark.eval.models.evaluation import (
                EvaluationDefinition,
                EvaluationVersion,
            )
            from ai_benchmark.eval.models.run import Run
            from ai_benchmark.eval.models.target import TargetConfiguration

            ed = EvaluationDefinition(name="retry-eval", execution_mode="sequential")
            db_session.add(ed)
            await db_session.flush()

            ev = EvaluationVersion(
                evaluation_id=ed.id,
                version_number=1,
                dataset_version_id=dv.id,
                scorer_config="[]",
            )
            db_session.add(ev)
            await db_session.flush()

            tc_target = TargetConfiguration(
                name="retry-target",
                model_name="gpt-4o",
                provider="openai",
                inference_params="{}",
            )
            db_session.add(tc_target)
            await db_session.flush()

            run = Run(
                evaluation_version_id=ev.id,
                target_config_id=tc_target.id,
                dataset_version_id=dv.id,
                status="running",
                total_items=1,
            )
            db_session.add(run)
            await db_session.flush()

            executor = ItemExecutor(provider="openai", max_retries=2)
            item_result = await executor.execute_item(db_session, run.id, cases[0], 0)

            assert item_result.raw_output == "OK"
            assert item_result.error_message is None
            assert mock_adapter.generate.call_count == 2
