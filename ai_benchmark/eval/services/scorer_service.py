"""Scorer and ScorerVersion CRUD service."""

from __future__ import annotations

import json

from sqlalchemy import select

from ..models.scorer import Scorer, ScorerVersion
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_scorer(
    session: AsyncSession,
    *,
    name: str,
    scorer_type: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> Scorer:
    s = Scorer(
        name=name,
        scorer_type=scorer_type,
        description=description,
        tags=json.dumps(tags) if tags else None,
    )
    session.add(s)
    await session.flush()
    return s


async def list_scorers(
    session: AsyncSession,
    *,
    scorer_type: str | None = None,
    name: str | None = None,
    include_archived: bool = False,
) -> list[Scorer]:
    stmt = select(Scorer)
    if not include_archived:
        stmt = stmt.where(Scorer.is_archived == False)  # noqa: E712
    if scorer_type:
        stmt = stmt.where(Scorer.scorer_type == scorer_type)
    if name:
        stmt = stmt.where(Scorer.name.ilike(f"%{name}%"))
    stmt = stmt.order_by(Scorer.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_scorer(session: AsyncSession, scorer_id: int) -> Scorer | None:
    return await session.get(Scorer, scorer_id)


async def create_version(
    session: AsyncSession,
    *,
    scorer_id: int,
    config: dict,
    implementation_ref: str | None = None,
    notes: str | None = None,
) -> ScorerVersion:
    """Create a new scorer version. Auto-increments version_number."""
    stmt = (
        select(ScorerVersion.version_number)
        .where(ScorerVersion.scorer_id == scorer_id)
        .order_by(ScorerVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    last_version = result.scalar()
    next_version = (last_version or 0) + 1

    sv = ScorerVersion(
        scorer_id=scorer_id,
        version_number=next_version,
        config=json.dumps(config),
        implementation_ref=implementation_ref,
        notes=notes,
    )
    session.add(sv)
    await session.flush()
    return sv


async def get_version(
    session: AsyncSession, scorer_id: int, version_number: int
) -> ScorerVersion | None:
    stmt = select(ScorerVersion).where(
        ScorerVersion.scorer_id == scorer_id,
        ScorerVersion.version_number == version_number,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
