"""Runner-machine compatibility rules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models.machine import MachineProfile
from ..models.runner import RunnerProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Static compatibility matrix: runner_class -> set of supported hardware_classes.
# Used as fallback when RunnerProfile.supported_machine_classes is not populated.
DEFAULT_COMPATIBILITY: dict[str, set[str]] = {
    "ollama": {
        "dgx_spark",
        "apple_silicon_pro",
        "apple_silicon_mini",
        "rtx_desktop",
        "intel_ai_laptop",
        "old_gpu_laptop",
    },
    "lmstudio": {
        "dgx_spark",
        "apple_silicon_pro",
        "apple_silicon_mini",
        "rtx_desktop",
        "intel_ai_laptop",
        "old_gpu_laptop",
    },
    "llamacpp": {
        "dgx_spark",
        "apple_silicon_pro",
        "apple_silicon_mini",
        "rtx_desktop",
        "intel_ai_laptop",
        "old_gpu_laptop",
        "edge_device",
    },
    "mlx": {
        "apple_silicon_pro",
        "apple_silicon_mini",
    },
    "vllm": {
        "dgx_spark",
        "rtx_desktop",
    },
    "sglang": {
        "dgx_spark",
        "rtx_desktop",
    },
    "tensorrt": {
        "dgx_spark",
        "rtx_desktop",
    },
    "openvino": {
        "intel_ai_laptop",
    },
}


def is_compatible(runner_class: str, hardware_class: str) -> bool:
    """Check static compatibility between a runner class and hardware class."""
    supported = DEFAULT_COMPATIBILITY.get(runner_class, set())
    return hardware_class in supported


def is_runner_compatible_with_machine(runner: RunnerProfile, machine: MachineProfile) -> bool:
    """Check if a RunnerProfile is compatible with a MachineProfile.

    Uses the runner's stored supported_machine_classes if populated,
    otherwise falls back to the static DEFAULT_COMPATIBILITY matrix.
    """
    if runner.supported_machine_classes:
        supported = json.loads(runner.supported_machine_classes)
        return machine.hardware_class in supported
    return is_compatible(runner.runner_class, machine.hardware_class)


async def get_compatible_runners(session: AsyncSession, hardware_class: str) -> list[RunnerProfile]:
    """Return all active runners compatible with a given hardware class."""
    result = await session.execute(
        select(RunnerProfile).where(RunnerProfile.is_archived == False)  # noqa: E712
    )
    runners = list(result.scalars().all())
    return [r for r in runners if _runner_supports_class(r, hardware_class)]


async def get_compatible_machines(session: AsyncSession, runner_class: str) -> list[MachineProfile]:
    """Return all machines compatible with a given runner class."""
    result = await session.execute(select(MachineProfile))
    machines = list(result.scalars().all())
    supported = DEFAULT_COMPATIBILITY.get(runner_class, set())
    return [m for m in machines if m.hardware_class in supported]


def _runner_supports_class(runner: RunnerProfile, hardware_class: str) -> bool:
    if runner.supported_machine_classes:
        supported = json.loads(runner.supported_machine_classes)
        return hardware_class in supported
    return is_compatible(runner.runner_class, hardware_class)
