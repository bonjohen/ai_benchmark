"""Runner profile CRUD and registry service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.runner import RunnerProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_runner(session: AsyncSession, **kwargs) -> RunnerProfile:
    """Create a new runner profile."""
    runner = RunnerProfile(**kwargs)
    session.add(runner)
    await session.flush()
    await session.refresh(runner)
    return runner


async def list_runners(
    session: AsyncSession,
    *,
    runner_class: str | None = None,
    include_archived: bool = False,
) -> list[RunnerProfile]:
    """List runner profiles with optional filters."""
    stmt = select(RunnerProfile)
    if runner_class:
        stmt = stmt.where(RunnerProfile.runner_class == runner_class)
    if not include_archived:
        stmt = stmt.where(RunnerProfile.is_archived == False)  # noqa: E712
    result = await session.execute(stmt.order_by(RunnerProfile.name))
    return list(result.scalars().all())


async def get_runner(session: AsyncSession, runner_id: int) -> RunnerProfile | None:
    """Get a runner profile by ID."""
    return await session.get(RunnerProfile, runner_id)


async def update_runner(session: AsyncSession, runner_id: int, **kwargs) -> RunnerProfile | None:
    """Update a runner profile."""
    runner = await session.get(RunnerProfile, runner_id)
    if runner is None:
        return None
    for key, value in kwargs.items():
        setattr(runner, key, value)
    await session.flush()
    await session.refresh(runner)
    return runner


async def get_runner_by_class(session: AsyncSession, runner_class: str) -> RunnerProfile | None:
    """Get a runner profile by runner_class name."""
    stmt = select(RunnerProfile).where(RunnerProfile.runner_class == runner_class)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
