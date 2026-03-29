"""Dataset, DatasetVersion, and TestCase CRUD service."""

from __future__ import annotations

import hashlib
import json
import random
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from ..models.dataset import Dataset, DatasetVersion, TestCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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


async def create_subset(
    session: AsyncSession,
    *,
    dataset_version_id: int,
    max_items: int | None = None,
    tags: list[str] | None = None,
    task_families: list[str] | None = None,
    seed: int | None = None,
    notes: str | None = None,
) -> DatasetVersion:
    """Create a new dataset version from a subset of items.

    Useful for smoke tests or focused evaluation sets.
    Applies tag/task_family filters first, then samples down to max_items.
    """
    dv = await session.get(DatasetVersion, dataset_version_id)
    if dv is None:
        raise ValueError(f"DatasetVersion {dataset_version_id} not found")

    stmt = (
        select(TestCase)
        .where(TestCase.dataset_version_id == dataset_version_id)
        .order_by(TestCase.item_index)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    # Filter by metadata
    if tags or task_families:
        filtered = []
        for item in items:
            if not item.metadata_json:
                continue
            meta = json.loads(item.metadata_json)
            if tags and not set(tags).intersection(meta.get("tags", [])):
                continue
            if task_families and meta.get("task_family") not in task_families:
                continue
            filtered.append(item)
        items = filtered

    # Sample if needed
    if max_items and len(items) > max_items:
        rng = random.Random(seed)
        items = rng.sample(items, max_items)
        items.sort(key=lambda tc: tc.item_index)

    # Build item dicts for create_version
    new_items = []
    for item in items:
        d: dict[str, Any] = {"input_text": item.input_text}
        if item.expected_output:
            d["expected_output"] = item.expected_output
        if item.context:
            d["context"] = item.context
        if item.metadata_json:
            d["metadata"] = json.loads(item.metadata_json)
        new_items.append(d)

    subset_notes = notes or f"Subset of version {dataset_version_id}"
    if max_items:
        subset_notes += f" (max_items={max_items})"
    if tags:
        subset_notes += f" (tags={tags})"

    return await create_version(
        session,
        dataset_id=dv.dataset_id,
        items=new_items,
        notes=subset_notes,
    )


async def preview_version(
    session: AsyncSession,
    dataset_version_id: int,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """Return a summary preview of a dataset version for validation."""
    dv = await session.get(DatasetVersion, dataset_version_id)
    if dv is None:
        raise ValueError(f"DatasetVersion {dataset_version_id} not found")

    stmt = (
        select(TestCase)
        .where(TestCase.dataset_version_id == dataset_version_id)
        .order_by(TestCase.item_index)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    # Collect metadata statistics
    task_families: set[str] = set()
    difficulties: set[str] = set()
    has_expected = 0
    for item in items:
        if item.expected_output:
            has_expected += 1
        if item.metadata_json:
            meta = json.loads(item.metadata_json)
            if "task_family" in meta:
                task_families.add(meta["task_family"])
            if "difficulty" in meta:
                difficulties.add(meta["difficulty"])

    sample = [
        {
            "index": item.item_index,
            "input_text": item.input_text[:200],
            "has_expected": item.expected_output is not None,
        }
        for item in items[:limit]
    ]

    return {
        "dataset_version_id": dv.id,
        "dataset_id": dv.dataset_id,
        "version_number": dv.version_number,
        "item_count": dv.item_count,
        "checksum": dv.checksum,
        "items_with_expected_output": has_expected,
        "task_families": sorted(task_families),
        "difficulties": sorted(difficulties),
        "sample_items": sample,
    }
