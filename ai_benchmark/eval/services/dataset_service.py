"""Dataset, DatasetVersion, and TestCase CRUD service."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.dataset import Dataset, DatasetVersion, TestCase


async def create_dataset(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
) -> Dataset:
    ds = Dataset(
        name=name,
        description=description,
        source=source,
        tags=json.dumps(tags) if tags else None,
    )
    session.add(ds)
    await session.flush()
    return ds


async def list_datasets(
    session: AsyncSession,
    *,
    name: str | None = None,
    source: str | None = None,
    include_archived: bool = False,
) -> list[Dataset]:
    stmt = select(Dataset)
    if not include_archived:
        stmt = stmt.where(Dataset.is_archived == False)  # noqa: E712
    if name:
        stmt = stmt.where(Dataset.name.ilike(f"%{name}%"))
    if source:
        stmt = stmt.where(Dataset.source == source)
    stmt = stmt.order_by(Dataset.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_dataset(session: AsyncSession, dataset_id: int) -> Dataset | None:
    return await session.get(Dataset, dataset_id)


async def create_version(
    session: AsyncSession,
    *,
    dataset_id: int,
    items: list[dict[str, Any]],
    notes: str | None = None,
) -> DatasetVersion:
    """Create a new dataset version with test cases.

    Auto-increments version_number, computes checksum, sets item_count.
    Each item dict should have: input_text, expected_output?, context?, metadata?
    """
    # Get next version number
    stmt = (
        select(DatasetVersion.version_number)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    last_version = result.scalar()
    next_version = (last_version or 0) + 1

    # Compute checksum from serialized items
    items_json = json.dumps(items, sort_keys=True)
    checksum = hashlib.sha256(items_json.encode()).hexdigest()

    dv = DatasetVersion(
        dataset_id=dataset_id,
        version_number=next_version,
        item_count=len(items),
        checksum=checksum,
        notes=notes,
    )
    session.add(dv)
    await session.flush()

    # Create test cases
    for idx, item in enumerate(items):
        metadata = item.get("metadata")
        tc = TestCase(
            dataset_version_id=dv.id,
            item_index=idx,
            input_text=item["input_text"],
            expected_output=item.get("expected_output"),
            context=item.get("context"),
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        session.add(tc)
    await session.flush()

    return dv


async def get_version(
    session: AsyncSession, dataset_id: int, version_number: int
) -> DatasetVersion | None:
    stmt = select(DatasetVersion).where(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.version_number == version_number,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_items(
    session: AsyncSession,
    dataset_version_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
    tag: str | None = None,
    difficulty: str | None = None,
    modality: str | None = None,
) -> list[TestCase]:
    stmt = (
        select(TestCase)
        .where(TestCase.dataset_version_id == dataset_version_id)
        .order_by(TestCase.item_index)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    # Post-query filter on JSON metadata fields
    if tag or difficulty or modality:
        filtered = []
        for item in items:
            if not item.metadata_json:
                continue
            meta = json.loads(item.metadata_json)
            if tag and tag not in meta.get("tags", []):
                continue
            if difficulty and meta.get("difficulty") != difficulty:
                continue
            if modality and meta.get("modality") != modality:
                continue
            filtered.append(item)
        return filtered

    return items


async def filter_items(
    session: AsyncSession,
    dataset_version_id: int,
    *,
    tags: list[str] | None = None,
    task_families: list[str] | None = None,
    min_tokens: int | None = None,
    max_tokens: int | None = None,
) -> list[int]:
    """Filter items by metadata query. Returns list of TestCase IDs."""
    stmt = (
        select(TestCase)
        .where(TestCase.dataset_version_id == dataset_version_id)
        .order_by(TestCase.item_index)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    matching_ids: list[int] = []
    for item in items:
        if not item.metadata_json:
            continue
        meta = json.loads(item.metadata_json)
        if tags and not set(tags).intersection(meta.get("tags", [])):
            continue
        if task_families and meta.get("task_family") not in task_families:
            continue
        token_est = meta.get("token_estimate", 0)
        if min_tokens and token_est < min_tokens:
            continue
        if max_tokens and token_est > max_tokens:
            continue
        matching_ids.append(item.id)

    return matching_ids
