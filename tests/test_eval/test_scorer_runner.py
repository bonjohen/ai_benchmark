"""Tests for scoring engine — individual scorers and ScorerRunner dispatch."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.run import Run, RunAggregateMetric, RunItemResult
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.eval.scoring.base import _SCORER_REGISTRY, resolve_scorer
from ai_benchmark.eval.scoring.builtin.exact_match import ExactMatchScorer, FuzzyMatchScorer
from ai_benchmark.eval.scoring.builtin.format_validator import FormatValidatorScorer
from ai_benchmark.eval.scoring.builtin.latency_cost import LatencyCostScorer
from ai_benchmark.eval.scoring.builtin.model_judge import ModelJudgeScorer
from ai_benchmark.eval.scoring.builtin.safety import SafetyScorer
from ai_benchmark.eval.scoring.scorer_runner import ScorerRunner
from ai_benchmark.models.base import create_session_factory

# ── Fixtures ──


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# ── Registry ──


class TestScorerRegistry:
    def test_all_builtin_scorers_registered(self):
        assert "exact_match" in _SCORER_REGISTRY
        assert "fuzzy_match" in _SCORER_REGISTRY
        assert "rubric" in _SCORER_REGISTRY
        assert "format_validator" in _SCORER_REGISTRY
        assert "latency_cost" in _SCORER_REGISTRY
        assert "safety" in _SCORER_REGISTRY
        assert "model_judge" in _SCORER_REGISTRY

    def test_resolve_unknown_scorer_raises(self):
        with pytest.raises(ValueError, match="No scorer registered"):
            resolve_scorer("nonexistent", {})


# ── ExactMatchScorer ──


class TestExactMatch:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        scorer = ExactMatchScorer({"case_sensitive": True})
        r = await scorer.score(output="hello", expected="hello")
        assert r.score == 1.0
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_exact_mismatch(self):
        scorer = ExactMatchScorer({"case_sensitive": True})
        r = await scorer.score(output="Hello", expected="hello")
        assert r.score == 0.0
        assert r.passed is False

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        scorer = ExactMatchScorer({"case_sensitive": False})
        r = await scorer.score(output="Hello", expected="hello")
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_strip_whitespace(self):
        scorer = ExactMatchScorer({"strip_whitespace": True})
        r = await scorer.score(output="  hello  ", expected="hello")
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_no_expected(self):
        scorer = ExactMatchScorer({})
        r = await scorer.score(output="hello", expected=None)
        assert r.score == 0.0


# ── FuzzyMatchScorer ──


class TestFuzzyMatch:
    @pytest.mark.asyncio
    async def test_identical_strings(self):
        scorer = FuzzyMatchScorer({"threshold": 0.85})
        r = await scorer.score(output="hello world", expected="hello world")
        assert r.score == 1.0
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_similar_strings(self):
        scorer = FuzzyMatchScorer({"threshold": 0.5})
        r = await scorer.score(output="hello world", expected="hello worl")
        assert r.score > 0.8
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_token_overlap(self):
        scorer = FuzzyMatchScorer({"method": "token_overlap", "threshold": 0.5})
        r = await scorer.score(output="the quick brown fox", expected="the brown fox jumps")
        # 3 of 4 expected tokens present
        assert r.score == pytest.approx(0.75)
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        scorer = FuzzyMatchScorer({"threshold": 0.95})
        r = await scorer.score(output="abc", expected="xyz")
        assert r.passed is False


# ── FormatValidatorScorer ──


class TestFormatValidator:
    @pytest.mark.asyncio
    async def test_valid_json(self):
        scorer = FormatValidatorScorer({"expected_format": "json"})
        r = await scorer.score(output='{"key": "value"}')
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        scorer = FormatValidatorScorer({"expected_format": "json"})
        r = await scorer.score(output="not json")
        assert r.score == 0.0
        assert r.details["errors"]

    @pytest.mark.asyncio
    async def test_valid_xml(self):
        scorer = FormatValidatorScorer({"expected_format": "xml"})
        r = await scorer.score(output="<root><child>text</child></root>")
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_xml(self):
        scorer = FormatValidatorScorer({"expected_format": "xml"})
        r = await scorer.score(output="<unclosed>")
        assert r.score == 0.0

    @pytest.mark.asyncio
    async def test_valid_markdown(self):
        scorer = FormatValidatorScorer({"expected_format": "markdown"})
        r = await scorer.score(output="# Title\n\nSome text")
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_valid_code(self):
        scorer = FormatValidatorScorer({"expected_format": "code"})
        r = await scorer.score(output="def foo():\n    return 42")
        assert r.score == 1.0


# ── LatencyCostScorer ──


class TestLatencyCost:
    @pytest.mark.asyncio
    async def test_under_threshold(self):
        scorer = LatencyCostScorer({"latency_threshold_ms": 1000, "token_budget": 500})
        r = await scorer.score(
            output="ok",
            metadata={"latency_ms": 200, "total_tokens": 100},
        )
        assert r.score == 1.0
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_over_threshold(self):
        scorer = LatencyCostScorer({"latency_threshold_ms": 100})
        r = await scorer.score(
            output="ok",
            metadata={"latency_ms": 500},
        )
        assert r.score == 0.0
        assert r.passed is False

    @pytest.mark.asyncio
    async def test_no_thresholds(self):
        scorer = LatencyCostScorer({})
        r = await scorer.score(output="ok")
        assert r.score == 1.0


# ── SafetyScorer ──


class TestSafety:
    @pytest.mark.asyncio
    async def test_safe_content(self):
        scorer = SafetyScorer({"categories": ["violence", "hate_speech"]})
        r = await scorer.score(output="The weather is nice today")
        assert r.score == 1.0
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_flagged_content(self):
        scorer = SafetyScorer({"categories": ["violence"]})
        r = await scorer.score(output="Take this weapon and attack them")
        assert r.score == 0.0
        assert r.passed is False
        assert "violence" in r.details["flagged_categories"]


# ── ModelJudgeScorer ──


class TestModelJudge:
    @pytest.mark.asyncio
    async def test_judge_with_mock(self):
        from ai_benchmark.eval.execution.adapters.base import GenerationResult

        scorer = ModelJudgeScorer(
            {
                "judge_provider": "openai",
                "judge_model": "gpt-4o",
                "scale_min": 0,
                "scale_max": 5,
                "pass_threshold": 3,
            }
        )

        mock_result = GenerationResult(
            output_text='{"score": 4, "reasoning": "Good answer"}',
            latency_ms=100,
        )

        with patch("ai_benchmark.eval.scoring.builtin.model_judge.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            r = await scorer.score(
                output="42",
                expected="42",
                input_text="What is 6*7?",
            )
            assert r.score == pytest.approx(0.8)  # 4/5
            assert r.passed is True
            assert r.details["raw_score"] == 4

    @pytest.mark.asyncio
    async def test_judge_error(self):
        from ai_benchmark.eval.execution.adapters.base import GenerationResult

        scorer = ModelJudgeScorer({"judge_provider": "openai"})
        mock_result = GenerationResult(output_text="", error="Timeout")

        with patch("ai_benchmark.eval.scoring.builtin.model_judge.resolve_adapter") as mock_resolve:
            mock_adapter = AsyncMock()
            mock_adapter.generate.return_value = mock_result
            mock_resolve.return_value = mock_adapter

            r = await scorer.score(output="test")
            assert r.passed is False
            assert "error" in r.details


# ── ScorerRunner Integration ──


class TestScorerRunnerIntegration:
    @pytest.mark.asyncio
    async def test_score_run_with_exact_match(self, db_session):
        """Full integration: create run items, score them, verify results."""
        # Build full FK chain
        ds = Dataset(name="scorer-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()

        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
        db_session.add(dv)
        await db_session.flush()

        tc1 = TestCase(
            dataset_version_id=dv.id,
            item_index=0,
            input_text="Q1",
            expected_output="correct",
        )
        tc2 = TestCase(
            dataset_version_id=dv.id,
            item_index=1,
            input_text="Q2",
            expected_output="right",
        )
        db_session.add_all([tc1, tc2])
        await db_session.flush()

        scorer_obj = Scorer(name="test-exact", scorer_type="exact_match")
        db_session.add(scorer_obj)
        await db_session.flush()

        sv = ScorerVersion(
            scorer_id=scorer_obj.id,
            version_number=1,
            config=json.dumps({"case_sensitive": False, "strip_whitespace": True}),
        )
        db_session.add(sv)
        await db_session.flush()

        ed = EvaluationDefinition(name="scorer-eval", execution_mode="sequential")
        db_session.add(ed)
        await db_session.flush()

        ev = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dv.id,
            scorer_config=json.dumps(
                [{"scorer_version_id": sv.id, "weight": 1.0, "pass_threshold": 0.5}]
            ),
        )
        db_session.add(ev)
        await db_session.flush()

        target = TargetConfiguration(
            name="scorer-target",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(target)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
            status="scoring",
            total_items=2,
        )
        db_session.add(run)
        await db_session.flush()

        # Item 1: matches expected
        item1 = RunItemResult(
            run_id=run.id,
            test_case_id=tc1.id,
            item_index=0,
            input_sent="Q1",
            raw_output="correct",
            scorer_results="[]",
            latency_ms=50,
            total_tokens=10,
        )
        # Item 2: doesn't match
        item2 = RunItemResult(
            run_id=run.id,
            test_case_id=tc2.id,
            item_index=1,
            input_sent="Q2",
            raw_output="wrong",
            scorer_results="[]",
            latency_ms=75,
            total_tokens=15,
        )
        db_session.add_all([item1, item2])
        await db_session.flush()

        runner = ScorerRunner()
        await runner.score_run(db_session, run.id)

        # Verify item1 passed, item2 failed
        await db_session.refresh(item1)
        await db_session.refresh(item2)

        results1 = json.loads(item1.scorer_results)
        assert len(results1) == 1
        assert results1[0]["passed"] is True
        assert item1.overall_pass is True

        results2 = json.loads(item2.scorer_results)
        assert results2[0]["passed"] is False
        assert item2.overall_pass is False

    @pytest.mark.asyncio
    async def test_compute_aggregates(self, db_session):
        """Test aggregate metric computation."""
        ds = Dataset(name="agg-ds", source="manual")
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
                input_text=f"Q{i}",
                expected_output=f"A{i}",
            )
            db_session.add(tc)
            cases.append(tc)
        await db_session.flush()

        ed = EvaluationDefinition(name="agg-eval", execution_mode="sequential")
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

        target = TargetConfiguration(
            name="agg-target",
            model_name="test",
            provider="openai",
            inference_params="{}",
        )
        db_session.add(target)
        await db_session.flush()

        run = Run(
            evaluation_version_id=ev.id,
            target_config_id=target.id,
            dataset_version_id=dv.id,
            status="scoring",
            total_items=3,
        )
        db_session.add(run)
        await db_session.flush()

        # Create 3 items: 2 pass, 1 fail
        for i, tc in enumerate(cases):
            item = RunItemResult(
                run_id=run.id,
                test_case_id=tc.id,
                item_index=i,
                input_sent=f"Q{i}",
                raw_output=f"A{i}",
                scorer_results="[]",
                overall_pass=(i < 2),
                latency_ms=50.0 + i * 10,
                total_tokens=10 + i * 5,
            )
            db_session.add(item)
        await db_session.flush()

        runner = ScorerRunner()
        await runner.compute_aggregates(db_session, run.id)

        from sqlalchemy import select

        stmt = select(RunAggregateMetric).where(RunAggregateMetric.run_id == run.id)
        result = await db_session.execute(stmt)
        metrics = {m.metric_name: m.metric_value for m in result.scalars().all()}

        assert "pass_rate" in metrics
        assert metrics["pass_rate"] == pytest.approx(2 / 3)
        assert "avg_latency_ms" in metrics
        assert "total_tokens" in metrics
        assert metrics["total_tokens"] == 10 + 15 + 20
