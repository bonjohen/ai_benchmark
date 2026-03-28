"""EvaluationDefinition and EvaluationVersion CRUD service."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.dataset import DatasetVersion
from ..models.evaluation import EvaluationDefinition, EvaluationVersion


async def create_evaluation(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    owner: str | None = None,
    tags: list[str] | None = None,
    suite_name: str | None = None,
    execution_mode: str = "sequential",
) -> EvaluationDefinition:
    ed = EvaluationDefinition(
        name=name,
        description=description,
        owner=owner,
        tags=json.dumps(tags) if tags else None,
        suite_name=suite_name,
        execution_mode=execution_mode,
    )
    session.add(ed)
    await session.flush()
    return ed


async def list_evaluations(
    session: AsyncSession,
    *,
    name: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
) -> list[EvaluationDefinition]:
    stmt = select(EvaluationDefinition)
    if not include_archived:
        stmt = stmt.where(EvaluationDefinition.is_archived == False)  # noqa: E712
    if name:
        stmt = stmt.where(EvaluationDefinition.name.ilike(f"%{name}%"))
    stmt = stmt.order_by(EvaluationDefinition.created_at.desc())
    result = await session.execute(stmt)
    evals = list(result.scalars().all())

    if tag:
        filtered = []
        for e in evals:
            if e.tags and tag in json.loads(e.tags):
                filtered.append(e)
        return filtered
    return evals


async def get_evaluation(
    session: AsyncSession, evaluation_id: int
) -> EvaluationDefinition | None:
    return await session.get(EvaluationDefinition, evaluation_id)


async def update_evaluation(
    session: AsyncSession,
    evaluation_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    is_archived: bool | None = None,
) -> EvaluationDefinition | None:
    ed = await session.get(EvaluationDefinition, evaluation_id)
    if ed is None:
        return None
    if name is not None:
        ed.name = name
    if description is not None:
        ed.description = description
    if tags is not None:
        ed.tags = json.dumps(tags)
    if is_archived is not None:
        ed.is_archived = is_archived
    await session.flush()
    return ed


async def create_version(
    session: AsyncSession,
    *,
    evaluation_id: int,
    dataset_version_id: int,
    scorer_config: list[dict],
    prompt_template: str | None = None,
    preprocessing: dict | None = None,
    pass_criteria: dict | None = None,
    notes: str | None = None,
) -> EvaluationVersion:
    """Create a new evaluation version. Validates dataset_version exists. Auto-increments."""
    # Validate dataset version exists
    dv = await session.get(DatasetVersion, dataset_version_id)
    if dv is None:
        raise ValueError(f"DatasetVersion {dataset_version_id} not found")

    # Get next version number
    stmt = (
        select(EvaluationVersion.version_number)
        .where(EvaluationVersion.evaluation_id == evaluation_id)
        .order_by(EvaluationVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    last_version = result.scalar()
    next_version = (last_version or 0) + 1

    ev = EvaluationVersion(
        evaluation_id=evaluation_id,
        version_number=next_version,
        dataset_version_id=dataset_version_id,
        scorer_config=json.dumps(scorer_config),
        prompt_template=prompt_template,
        preprocessing=json.dumps(preprocessing) if preprocessing else None,
        pass_criteria=json.dumps(pass_criteria) if pass_criteria else None,
        notes=notes,
    )
    session.add(ev)
    await session.flush()
    return ev


async def get_version(
    session: AsyncSession, evaluation_id: int, version_number: int
) -> EvaluationVersion | None:
    stmt = select(EvaluationVersion).where(
        EvaluationVersion.evaluation_id == evaluation_id,
        EvaluationVersion.version_number == version_number,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
