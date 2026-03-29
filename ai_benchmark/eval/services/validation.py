"""Pre-run validation rules — ensures all dependencies exist before execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.dataset import DatasetVersion, TestCase
from ..models.evaluation import EvaluationVersion
from ..models.scorer import ScorerVersion
from ..models.target import TargetConfiguration

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ValidationResult:
    """Result of pre-run validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def validate_run_ready(
    session: AsyncSession,
    *,
    evaluation_version_id: int,
    target_config_id: int,
    dataset_version_id: int | None = None,
) -> ValidationResult:
    """Validate that all dependencies exist and are consistent for a run.

    Checks:
    1. EvaluationVersion exists
    2. TargetConfiguration exists and is not archived
    3. DatasetVersion exists and has items
    4. All scorer versions referenced in scorer_config exist
    5. Dataset version matches what the evaluation version expects
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Check evaluation version
    ev = await session.get(EvaluationVersion, evaluation_version_id)
    if ev is None:
        errors.append(f"EvaluationVersion {evaluation_version_id} not found")
        return ValidationResult(valid=False, errors=errors)

    # 2. Check target configuration
    target = await session.get(TargetConfiguration, target_config_id)
    if target is None:
        errors.append(f"TargetConfiguration {target_config_id} not found")
    elif target.is_archived:
        errors.append(f"TargetConfiguration '{target.name}' is archived")

    # 3. Check dataset version
    dv_id = dataset_version_id or ev.dataset_version_id
    dv = await session.get(DatasetVersion, dv_id)
    if dv is None:
        errors.append(f"DatasetVersion {dv_id} not found")
    else:
        # Check it has test cases
        count_result = await session.execute(
            select(TestCase.id).where(TestCase.dataset_version_id == dv_id).limit(1)
        )
        if count_result.scalar() is None:
            errors.append(f"DatasetVersion {dv_id} has no test cases")

    # 4. Check scorer versions
    if ev.scorer_config:
        scorer_configs = json.loads(ev.scorer_config)
        for i, sc in enumerate(scorer_configs):
            sv_id = sc.get("scorer_version_id")
            if sv_id is None:
                errors.append(f"Scorer config entry {i} missing scorer_version_id")
                continue
            sv = await session.get(ScorerVersion, sv_id)
            if sv is None:
                errors.append(f"ScorerVersion {sv_id} not found (scorer config entry {i})")

    # 5. Dataset version consistency
    if dataset_version_id and dataset_version_id != ev.dataset_version_id:
        warnings.append(
            f"Overriding evaluation's dataset version {ev.dataset_version_id} "
            f"with {dataset_version_id}"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


async def validate_evaluation_binding(
    session: AsyncSession,
    *,
    dataset_version_id: int,
    scorer_config: list[dict],
) -> ValidationResult:
    """Validate that a dataset version and scorer config are compatible for binding.

    Checks:
    1. DatasetVersion exists and has items
    2. All referenced scorer versions exist
    3. Weights sum to a positive number
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check dataset
    dv = await session.get(DatasetVersion, dataset_version_id)
    if dv is None:
        errors.append(f"DatasetVersion {dataset_version_id} not found")
    elif dv.item_count == 0:
        warnings.append(f"DatasetVersion {dataset_version_id} has 0 items")

    # Check scorer versions and weights
    total_weight = 0.0
    for i, sc in enumerate(scorer_config):
        sv_id = sc.get("scorer_version_id")
        weight = sc.get("weight", 1.0)
        if sv_id is None:
            errors.append(f"Scorer config entry {i} missing scorer_version_id")
            continue
        sv = await session.get(ScorerVersion, sv_id)
        if sv is None:
            errors.append(f"ScorerVersion {sv_id} not found (entry {i})")
        total_weight += weight

    if total_weight <= 0 and not errors:
        errors.append("Scorer weights must sum to a positive number")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
