"""Matrix expansion — turns one evaluation + many targets into a validated run group."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models.run import Run, RunGroup
from ..models.target import TargetConfiguration
from .validation import validate_run_ready, validate_target_compatibility

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class MatrixResult:
    """Result of matrix expansion."""

    run_group: RunGroup | None = None
    runs: list[Run] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def expand_matrix(
    session: AsyncSession,
    *,
    evaluation_version_id: int,
    target_config_ids: list[int],
    dataset_version_id: int,
    name: str | None = None,
    tags: list[str] | None = None,
    skip_incompatible: bool = True,
    validate: bool = True,
    total_items: int = 0,
) -> MatrixResult:
    """Expand one evaluation × N targets into a run group with child runs.

    For each target:
    1. Optionally validate target compatibility (runner × machine)
    2. Optionally validate run readiness (eval version, dataset, scorers)
    3. Create a child run in the group

    If skip_incompatible=True, incompatible targets are skipped with warnings.
    If False, any incompatibility is a hard error.
    """
    result = MatrixResult()

    if not target_config_ids:
        result.errors.append("No target configurations provided")
        return result

    # Create run group
    rg = RunGroup(
        name=name or f"matrix-{evaluation_version_id}",
        execution_type="matrix",
        tags=json.dumps(tags) if tags else None,
    )
    session.add(rg)
    await session.flush()
    result.run_group = rg

    from . import machine_service

    for target_id in target_config_ids:
        # Validate target compatibility
        if validate:
            compat = await validate_target_compatibility(session, target_id)
            if not compat.valid:
                if skip_incompatible:
                    result.skipped.append(
                        {
                            "target_config_id": target_id,
                            "reason": compat.errors,
                        }
                    )
                    continue
                else:
                    result.errors.extend(compat.errors)
                    continue

            readiness = await validate_run_ready(
                session,
                evaluation_version_id=evaluation_version_id,
                target_config_id=target_id,
                dataset_version_id=dataset_version_id,
            )
            if not readiness.valid:
                if skip_incompatible:
                    result.skipped.append(
                        {
                            "target_config_id": target_id,
                            "reason": readiness.errors,
                        }
                    )
                    continue
                else:
                    result.errors.extend(readiness.errors)
                    continue

        # Capture machine snapshot if target has a machine
        target = await session.get(TargetConfiguration, target_id)
        machine_snapshot_id = None
        requested_machine_id = None
        if target and target.machine_profile_id:
            requested_machine_id = target.machine_profile_id
            snap = await machine_service.capture_snapshot(session, target.machine_profile_id)
            machine_snapshot_id = snap.id

        run = Run(
            run_group_id=rg.id,
            evaluation_version_id=evaluation_version_id,
            target_config_id=target_id,
            dataset_version_id=dataset_version_id,
            requested_machine_profile_id=requested_machine_id,
            machine_snapshot_id=machine_snapshot_id,
            status="queued",
            trigger_type="matrix",
            total_items=total_items,
        )
        session.add(run)
        result.runs.append(run)

    await session.flush()
    return result
