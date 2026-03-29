"""Tests for dataset service CRUD operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from ai_benchmark.eval.models.dataset import TestCase
from ai_benchmark.eval.services import dataset_service
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


async def test_create_dataset(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(
        db_session,
        name="coding-eval",
        description="Coding tasks",
        source="manual",
        tags=["coding", "python"],
    )
    assert ds.id is not None
    assert ds.name == "coding-eval"
    assert json.loads(ds.tags) == ["coding", "python"]


async def test_list_datasets(db_session: AsyncSession):
    await dataset_service.create_dataset(db_session, name="ds-1")
    await dataset_service.create_dataset(db_session, name="ds-2", source="imported")
    all_ds = await dataset_service.list_datasets(db_session)
    assert len(all_ds) == 2


async def test_list_datasets_filter_by_source(db_session: AsyncSession):
    await dataset_service.create_dataset(db_session, name="ds-manual", source="manual")
    await dataset_service.create_dataset(db_session, name="ds-import", source="imported")
    results = await dataset_service.list_datasets(db_session, source="imported")
    assert len(results) == 1
    assert results[0].name == "ds-import"


async def test_create_version_auto_increments(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="versioned-ds")
    items = [{"input_text": "q1"}, {"input_text": "q2"}]
    v1 = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    assert v1.version_number == 1
    assert v1.item_count == 2
    assert v1.checksum is not None

    v2 = await dataset_service.create_version(
        db_session, dataset_id=ds.id, items=[{"input_text": "q3"}]
    )
    assert v2.version_number == 2
    assert v2.item_count == 1


async def test_create_version_computes_checksum(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="checksum-ds")
    items = [{"input_text": "hello"}]
    v1 = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    v2 = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    # Same items → same checksum
    assert v1.checksum == v2.checksum


async def test_create_version_inserts_test_cases(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="tc-ds")
    items = [
        {"input_text": "What is 2+2?", "expected_output": "4", "metadata": {"difficulty": "easy"}},
        {"input_text": "Explain recursion", "context": "CS interview"},
    ]
    v = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)

    stmt = select(TestCase).where(TestCase.dataset_version_id == v.id).order_by(TestCase.item_index)
    result = await db_session.execute(stmt)
    cases = list(result.scalars().all())
    assert len(cases) == 2
    assert cases[0].input_text == "What is 2+2?"
    assert cases[0].expected_output == "4"
    assert json.loads(cases[0].metadata_json) == {"difficulty": "easy"}
    assert cases[1].context == "CS interview"


async def test_get_version(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="get-v-ds")
    await dataset_service.create_version(db_session, dataset_id=ds.id, items=[{"input_text": "q"}])
    v = await dataset_service.get_version(db_session, ds.id, 1)
    assert v is not None
    assert v.version_number == 1


async def test_list_items(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="list-items-ds")
    items = [{"input_text": f"q{i}"} for i in range(5)]
    v = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    loaded = await dataset_service.list_items(db_session, v.id, limit=3)
    assert len(loaded) == 3
    assert loaded[0].item_index == 0


async def test_list_items_filter_by_tag(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="tag-filter-ds")
    items = [
        {"input_text": "q1", "metadata": {"tags": ["math"]}},
        {"input_text": "q2", "metadata": {"tags": ["coding"]}},
        {"input_text": "q3", "metadata": {"tags": ["math", "hard"]}},
    ]
    v = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    results = await dataset_service.list_items(db_session, v.id, tag="math")
    assert len(results) == 2


async def test_filter_items_by_task_family(db_session: AsyncSession):
    ds = await dataset_service.create_dataset(db_session, name="filter-ds")
    items = [
        {"input_text": "q1", "metadata": {"task_family": "math", "tags": ["easy"]}},
        {"input_text": "q2", "metadata": {"task_family": "coding", "tags": ["medium"]}},
    ]
    v = await dataset_service.create_version(db_session, dataset_id=ds.id, items=items)
    ids = await dataset_service.filter_items(db_session, v.id, task_families=["coding"])
    assert len(ids) == 1
