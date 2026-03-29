"""Tests for Phase 4: Evaluation definitions, datasets, scorers, and validation."""

from __future__ import annotations

import json

import pytest

from ai_benchmark.eval.services import dataset_service, eval_service, scorer_service
from ai_benchmark.eval.services.validation import (
    validate_evaluation_binding,
    validate_run_ready,
)


@pytest.fixture
async def session(db_engine_fk):
    from ai_benchmark.models.base import create_session_factory

    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


# --- Helper to create a full eval chain ---


async def _create_eval_chain(session):
    """Create a minimal evaluation chain and return all entities."""
    ds = await dataset_service.create_dataset(session, name="p4-ds")
    dv = await dataset_service.create_version(
        session,
        dataset_id=ds.id,
        items=[
            {
                "input_text": "What is 2+2?",
                "expected_output": "4",
                "metadata": {"task_family": "math", "difficulty": "easy", "tags": ["arithmetic"]},
            },
            {
                "input_text": "Capital of France?",
                "expected_output": "Paris",
                "metadata": {"task_family": "geography", "difficulty": "easy", "tags": ["trivia"]},
            },
            {
                "input_text": "Explain quantum entanglement",
                "expected_output": None,
                "metadata": {
                    "task_family": "science",
                    "difficulty": "hard",
                    "tags": ["physics", "open-ended"],
                },
            },
        ],
    )
    scorer = await scorer_service.create_scorer(session, name="p4-exact", scorer_type="exact_match")
    sv = await scorer_service.create_version(
        session, scorer_id=scorer.id, config={"case_sensitive": False}
    )
    ev = await eval_service.create_evaluation(session, name="p4-eval")
    evv = await eval_service.create_version(
        session,
        evaluation_id=ev.id,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
    )
    await session.commit()
    return ds, dv, scorer, sv, ev, evv


# --- Evaluation versioning ---


@pytest.mark.asyncio
async def test_evaluation_version_auto_increment(session):
    ev = await eval_service.create_evaluation(session, name="v-auto")
    ds = await dataset_service.create_dataset(session, name="v-auto-ds")
    dv = await dataset_service.create_version(
        session, dataset_id=ds.id, items=[{"input_text": "hi"}]
    )
    scorer = await scorer_service.create_scorer(session, name="v-auto-s", scorer_type="exact_match")
    sv = await scorer_service.create_version(session, scorer_id=scorer.id, config={})
    await session.flush()

    v1 = await eval_service.create_version(
        session,
        evaluation_id=ev.id,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
    )
    v2 = await eval_service.create_version(
        session,
        evaluation_id=ev.id,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
        notes="updated",
    )
    await session.commit()

    assert v1.version_number == 1
    assert v2.version_number == 2
    assert v1.id != v2.id


@pytest.mark.asyncio
async def test_evaluation_version_rejects_bad_dataset(session):
    ev = await eval_service.create_evaluation(session, name="bad-dv")
    await session.flush()

    with pytest.raises(ValueError, match="not found"):
        await eval_service.create_version(
            session,
            evaluation_id=ev.id,
            dataset_version_id=99999,
            scorer_config=[],
        )


# --- Dataset snapshotting ---


@pytest.mark.asyncio
async def test_dataset_version_checksum(session):
    ds = await dataset_service.create_dataset(session, name="checksum-ds")
    items = [{"input_text": "hello"}, {"input_text": "world"}]
    dv = await dataset_service.create_version(session, dataset_id=ds.id, items=items)
    await session.commit()

    assert dv.checksum is not None
    assert len(dv.checksum) == 64  # SHA256 hex digest


@pytest.mark.asyncio
async def test_dataset_version_item_count(session):
    ds = await dataset_service.create_dataset(session, name="count-ds")
    dv = await dataset_service.create_version(
        session,
        dataset_id=ds.id,
        items=[{"input_text": f"item-{i}"} for i in range(10)],
    )
    await session.commit()

    assert dv.item_count == 10


# --- Subset generation ---


@pytest.mark.asyncio
async def test_create_subset_max_items(session):
    ds, dv, *_ = await _create_eval_chain(session)

    subset = await dataset_service.create_subset(
        session,
        dataset_version_id=dv.id,
        max_items=2,
        seed=42,
    )
    await session.commit()

    assert subset.item_count == 2
    assert subset.version_number == 2  # auto-incremented
    assert "max_items=2" in subset.notes


@pytest.mark.asyncio
async def test_create_subset_by_tag(session):
    ds, dv, *_ = await _create_eval_chain(session)

    subset = await dataset_service.create_subset(
        session,
        dataset_version_id=dv.id,
        tags=["arithmetic"],
    )
    await session.commit()

    assert subset.item_count == 1  # only "What is 2+2?" matches


@pytest.mark.asyncio
async def test_create_subset_by_task_family(session):
    ds, dv, *_ = await _create_eval_chain(session)

    subset = await dataset_service.create_subset(
        session,
        dataset_version_id=dv.id,
        task_families=["math", "geography"],
    )
    await session.commit()

    assert subset.item_count == 2


@pytest.mark.asyncio
async def test_create_subset_preserves_expected_output(session):
    ds, dv, *_ = await _create_eval_chain(session)

    subset = await dataset_service.create_subset(
        session,
        dataset_version_id=dv.id,
        tags=["arithmetic"],
    )
    await session.commit()

    items = await dataset_service.list_items(session, subset.id)
    assert len(items) == 1
    assert items[0].expected_output == "4"


# --- Dataset preview ---


@pytest.mark.asyncio
async def test_preview_version(session):
    ds, dv, *_ = await _create_eval_chain(session)

    preview = await dataset_service.preview_version(session, dv.id)

    assert preview["item_count"] == 3
    assert preview["items_with_expected_output"] == 2  # "explain quantum..." has None
    assert "math" in preview["task_families"]
    assert "geography" in preview["task_families"]
    assert len(preview["sample_items"]) == 3
    assert preview["checksum"] is not None


@pytest.mark.asyncio
async def test_preview_version_limit(session):
    ds, dv, *_ = await _create_eval_chain(session)

    preview = await dataset_service.preview_version(session, dv.id, limit=1)
    assert len(preview["sample_items"]) == 1


@pytest.mark.asyncio
async def test_preview_version_not_found(session):
    with pytest.raises(ValueError, match="not found"):
        await dataset_service.preview_version(session, 99999)


# --- Scorer versioning ---


@pytest.mark.asyncio
async def test_scorer_version_auto_increment(session):
    scorer = await scorer_service.create_scorer(session, name="sv-auto", scorer_type="exact_match")
    v1 = await scorer_service.create_version(session, scorer_id=scorer.id, config={"v": 1})
    v2 = await scorer_service.create_version(session, scorer_id=scorer.id, config={"v": 2})
    await session.commit()

    assert v1.version_number == 1
    assert v2.version_number == 2
    assert json.loads(v1.config) == {"v": 1}
    assert json.loads(v2.config) == {"v": 2}


# --- Fuzzy match scorer ---


@pytest.mark.asyncio
async def test_fuzzy_match_scorer():
    from ai_benchmark.eval.scoring.builtin.fuzzy_match import FuzzyMatchScorer

    scorer = FuzzyMatchScorer({"threshold": 0.8})

    result = await scorer.score(output="hello world", expected="Hello World")
    assert result.passed
    assert result.score > 0.9

    result = await scorer.score(output="completely different text", expected="hello world")
    assert not result.passed
    assert result.score < 0.5


@pytest.mark.asyncio
async def test_fuzzy_match_scorer_case_sensitive():
    from ai_benchmark.eval.scoring.builtin.fuzzy_match import FuzzyMatchScorer

    scorer = FuzzyMatchScorer({"threshold": 1.0, "case_sensitive": True})
    result = await scorer.score(output="Hello", expected="hello")
    assert not result.passed


# --- Run validation ---


@pytest.mark.asyncio
async def test_validate_run_ready_valid(session):
    from ai_benchmark.eval.models.target import TargetConfiguration

    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = TargetConfiguration(
        name="p4-target",
        model_name="test-model",
        provider="ollama",
        inference_params="{}",
    )
    session.add(target)
    await session.flush()
    await session.commit()

    result = await validate_run_ready(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
    )
    assert result.valid
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_validate_run_ready_missing_eval_version(session):
    result = await validate_run_ready(
        session,
        evaluation_version_id=99999,
        target_config_id=1,
    )
    assert not result.valid
    assert any("EvaluationVersion" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_run_ready_archived_target(session):
    from ai_benchmark.eval.models.target import TargetConfiguration

    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    target = TargetConfiguration(
        name="archived-target",
        model_name="old-model",
        provider="ollama",
        inference_params="{}",
        is_archived=True,
    )
    session.add(target)
    await session.flush()
    await session.commit()

    result = await validate_run_ready(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
    )
    assert not result.valid
    assert any("archived" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_run_ready_missing_scorer(session):
    ds = await dataset_service.create_dataset(session, name="badsv-ds")
    dv = await dataset_service.create_version(
        session, dataset_id=ds.id, items=[{"input_text": "hi"}]
    )
    ev = await eval_service.create_evaluation(session, name="badsv-eval")
    from ai_benchmark.eval.models.evaluation import EvaluationVersion

    evv = EvaluationVersion(
        evaluation_id=ev.id,
        version_number=1,
        dataset_version_id=dv.id,
        scorer_config=json.dumps([{"scorer_version_id": 99999, "weight": 1.0}]),
    )
    session.add(evv)
    await session.flush()

    from ai_benchmark.eval.models.target import TargetConfiguration

    target = TargetConfiguration(
        name="badsv-target",
        model_name="m",
        provider="ollama",
        inference_params="{}",
    )
    session.add(target)
    await session.flush()
    await session.commit()

    result = await validate_run_ready(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
    )
    assert not result.valid
    assert any("ScorerVersion 99999 not found" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_run_ready_dataset_override_warning(session):
    from ai_benchmark.eval.models.target import TargetConfiguration

    ds, dv, scorer, sv, ev, evv = await _create_eval_chain(session)

    # Create a second dataset version
    ds2 = await dataset_service.create_dataset(session, name="p4-ds2")
    dv2 = await dataset_service.create_version(
        session, dataset_id=ds2.id, items=[{"input_text": "alt"}]
    )

    target = TargetConfiguration(
        name="override-target",
        model_name="m",
        provider="ollama",
        inference_params="{}",
    )
    session.add(target)
    await session.flush()
    await session.commit()

    result = await validate_run_ready(
        session,
        evaluation_version_id=evv.id,
        target_config_id=target.id,
        dataset_version_id=dv2.id,
    )
    assert result.valid
    assert len(result.warnings) == 1
    assert "Overriding" in result.warnings[0]


# --- Evaluation binding validation ---


@pytest.mark.asyncio
async def test_validate_evaluation_binding_valid(session):
    ds, dv, scorer, sv, *_ = await _create_eval_chain(session)

    result = await validate_evaluation_binding(
        session,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": sv.id, "weight": 1.0}],
    )
    assert result.valid


@pytest.mark.asyncio
async def test_validate_evaluation_binding_missing_dataset(session):
    result = await validate_evaluation_binding(
        session,
        dataset_version_id=99999,
        scorer_config=[],
    )
    assert not result.valid
    assert any("DatasetVersion" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_evaluation_binding_bad_scorer(session):
    ds = await dataset_service.create_dataset(session, name="bind-ds")
    dv = await dataset_service.create_version(
        session, dataset_id=ds.id, items=[{"input_text": "x"}]
    )
    await session.commit()

    result = await validate_evaluation_binding(
        session,
        dataset_version_id=dv.id,
        scorer_config=[{"scorer_version_id": 99999, "weight": 1.0}],
    )
    assert not result.valid
    assert any("ScorerVersion 99999" in e for e in result.errors)
