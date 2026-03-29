"""Privacy enforcement — local-only guards and data classification."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Providers considered local (data never leaves the machine)
LOCAL_PROVIDERS = frozenset(
    {
        "ollama",
        "lmstudio",
        "llamacpp",
        "mlx",
        "vllm",
        "sglang",
        "tensorrt",
        "openvino",
        "local",
    }
)

# Providers that send data to remote endpoints
REMOTE_PROVIDERS = frozenset(
    {
        "openai",
        "anthropic",
        "generic_http",
    }
)


def is_local_provider(provider: str) -> bool:
    """Return True if the provider runs entirely on the local machine."""
    return provider.lower() in LOCAL_PROVIDERS


async def enforce_local_only(
    session: AsyncSession,
    *,
    dataset_id: int | None = None,
    run_id: int | None = None,
    target_config_id: int,
) -> list[str]:
    """Check local-only constraints before execution.

    Returns a list of violation messages. Empty list means all checks pass.
    """
    from ..models.dataset import Dataset
    from ..models.run import Run
    from ..models.target import TargetConfiguration

    violations: list[str] = []

    target = await session.get(TargetConfiguration, target_config_id)
    if target is None:
        violations.append(f"Target {target_config_id} not found")
        return violations

    provider_is_local = is_local_provider(target.provider)

    # Check if dataset is local-only
    if dataset_id:
        ds = await session.get(Dataset, dataset_id)
        if ds and ds.is_local_only and not provider_is_local:
            violations.append(
                f"Dataset '{ds.name}' is marked local-only but target "
                f"'{target.name}' uses remote provider '{target.provider}'"
            )

    # Check if run is marked local-only
    if run_id:
        run = await session.get(Run, run_id)
        if run and run.is_local_only and not provider_is_local:
            violations.append(
                f"Run {run_id} is marked local-only but target "
                f"'{target.name}' uses remote provider '{target.provider}'"
            )

    # Check if target itself is local-only
    if target.is_local_only and not provider_is_local:
        violations.append(
            f"Target '{target.name}' is marked local-only but "
            f"uses remote provider '{target.provider}'"
        )

    if violations:
        logger.warning(
            "local_only_violation",
            target=target.name,
            provider=target.provider,
            violations=violations,
        )

    return violations


async def classify_run_privacy(
    session: AsyncSession,
    run_id: int,
) -> dict:
    """Return a privacy classification for a run.

    Useful for display in the UI and audit reports.
    """
    from ..models.run import Run
    from ..models.target import TargetConfiguration

    run = await session.get(Run, run_id)
    if run is None:
        return {"run_id": run_id, "classification": "unknown"}

    target = await session.get(TargetConfiguration, run.target_config_id)
    provider = target.provider if target else "unknown"
    local = is_local_provider(provider)

    return {
        "run_id": run_id,
        "provider": provider,
        "is_local_provider": local,
        "is_local_only_flag": run.is_local_only,
        "classification": "local" if local else "remote",
        "data_destination": "localhost" if local else target.endpoint_url or provider,
    }
