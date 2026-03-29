"""Run dispatch — machine-aware and runner-aware job routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..models.machine import MachineProfile
from ..models.run import Run
from ..models.runner import RunnerProfile
from ..models.target import TargetConfiguration
from ..services.compatibility import is_compatible

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Valid run lifecycle states
RUN_STATES = (
    "queued",
    "validating",
    "preparing",
    "running_generation",
    "running_scorers",
    "aggregating",
    "completed",
    "partially_completed",
    "failed",
    "blocked",
    "canceled",
)

TERMINAL_STATES = ("completed", "partially_completed", "failed", "canceled")
ACTIVE_STATES = ("validating", "preparing", "running_generation", "running_scorers", "aggregating")


@dataclass
class RunConstraints:
    """Constraints that must be satisfied before and during a run."""

    local_only: bool = False
    machine_allow_list: list[str] | None = None  # hardware_class values
    runner_allow_list: list[str] | None = None  # runner_class values
    cost_cap_usd: float | None = None
    time_cap_seconds: int | None = None
    max_concurrent_runs: int = 5


@dataclass
class DispatchDecision:
    """Result of dispatch evaluation."""

    allowed: bool
    reason: str = ""
    machine_profile_id: int | None = None
    runner_profile_id: int | None = None


async def evaluate_dispatch(
    session: AsyncSession,
    run: Run,
    constraints: RunConstraints | None = None,
) -> DispatchDecision:
    """Evaluate whether a run can be dispatched given constraints.

    Checks:
    1. Target exists and has a valid provider
    2. Machine compatibility (if machine is assigned)
    3. Runner allow-list
    4. Machine allow-list
    5. Local-only constraint
    6. Concurrent run limits
    """
    constraints = constraints or RunConstraints()

    target = await session.get(TargetConfiguration, run.target_config_id)
    if target is None:
        return DispatchDecision(allowed=False, reason=f"Target {run.target_config_id} not found")

    # Local-only check
    if constraints.local_only and not run.is_local_only:
        return DispatchDecision(
            allowed=False,
            reason="Constraint requires local-only runs",
        )

    # Runner allow-list
    if constraints.runner_allow_list and target.provider not in constraints.runner_allow_list:
        return DispatchDecision(
            allowed=False,
            reason=f"Provider '{target.provider}' not in runner allow-list",
        )

    # Machine allow-list
    if constraints.machine_allow_list and target.machine_profile_id:
        machine = await session.get(MachineProfile, target.machine_profile_id)
        if machine and machine.hardware_class not in constraints.machine_allow_list:
            return DispatchDecision(
                allowed=False,
                reason=f"Machine class '{machine.hardware_class}' not in allow-list",
            )

    # Machine-runner compatibility
    if target.machine_profile_id and target.runner_profile_id:
        machine = await session.get(MachineProfile, target.machine_profile_id)
        runner = await session.get(RunnerProfile, target.runner_profile_id)
        if machine and runner and not is_compatible(runner.runner_class, machine.hardware_class):
            return DispatchDecision(
                allowed=False,
                reason=(
                    f"Runner '{runner.runner_class}' incompatible with "
                    f"machine '{machine.hardware_class}'"
                ),
            )

    # Concurrent run limit
    active_count_stmt = select(Run.id).where(Run.status.in_(ACTIVE_STATES))
    active_result = await session.execute(active_count_stmt)
    active_count = len(active_result.all())
    if active_count >= constraints.max_concurrent_runs:
        return DispatchDecision(
            allowed=False,
            reason=(
                f"Concurrent run limit reached ({active_count}/{constraints.max_concurrent_runs})"
            ),
        )

    logger.info(
        "dispatch_allowed",
        run_id=run.id,
        target=target.name,
        provider=target.provider,
    )

    return DispatchDecision(
        allowed=True,
        machine_profile_id=target.machine_profile_id,
        runner_profile_id=target.runner_profile_id,
    )


async def get_queue(
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[Run]:
    """Get queued runs ordered by priority (highest first), then creation time."""
    stmt = (
        select(Run)
        .where(Run.status == "queued")
        .order_by(Run.priority.desc(), Run.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def resume_run(
    session: AsyncSession,
    run_id: int,
) -> Run:
    """Resume a failed or partially completed run by re-queuing it.

    Does not re-execute already-completed items — the orchestrator
    should skip items that already have results.
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    if run.status not in ("failed", "partially_completed"):
        raise ValueError(f"Cannot resume run in '{run.status}' state")

    run.status = "queued"
    run.error_message = None
    await session.flush()

    logger.info(
        "run_resumed",
        run_id=run_id,
        previous_completed=run.completed_items,
        previous_failed=run.failed_items,
    )
    return run


async def get_run_progress(
    session: AsyncSession,
    run_id: int,
) -> dict:
    """Get progress metrics for a single run."""
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    total = run.total_items or 1
    processed = run.completed_items + run.failed_items + run.skipped_items

    return {
        "run_id": run.id,
        "status": run.status,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
        "failed_items": run.failed_items,
        "skipped_items": run.skipped_items,
        "processed_items": processed,
        "progress_pct": round(processed / total * 100, 1) if total > 0 else 0.0,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


async def get_group_progress(
    session: AsyncSession,
    run_group_id: int,
) -> dict:
    """Get progress metrics for a run group (matrix/batch)."""
    from ..models.run import RunGroup

    rg = await session.get(RunGroup, run_group_id)
    if rg is None:
        raise ValueError(f"RunGroup {run_group_id} not found")

    stmt = select(Run).where(Run.run_group_id == run_group_id)
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    status_counts: dict[str, int] = {}
    total_items = 0
    completed_items = 0
    failed_items = 0

    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        total_items += run.total_items
        completed_items += run.completed_items
        failed_items += run.failed_items

    return {
        "run_group_id": run_group_id,
        "name": rg.name,
        "execution_type": rg.execution_type,
        "total_runs": len(runs),
        "status_counts": status_counts,
        "total_items": total_items,
        "completed_items": completed_items,
        "failed_items": failed_items,
        "progress_pct": round((completed_items + failed_items) / total_items * 100, 1)
        if total_items > 0
        else 0.0,
    }
