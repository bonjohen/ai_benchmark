"""Shared serialization helpers for eval API routes.

These functions convert ORM model instances to plain dicts suitable for API
responses.  Both the run and target route modules import from here so that
field-set changes only need to happen in one place.
"""

from __future__ import annotations

import json

# Keys to redact from runtime_options in API responses
_REDACT_KEYS = {"api_key", "secret_key", "token", "password"}


def _redact_keys(d: dict | None) -> dict | None:
    """Remove sensitive keys from a dict before returning in API responses."""
    if d is None:
        return None
    return {k: "***REDACTED***" if k in _REDACT_KEYS else v for k, v in d.items()}


def run_to_dict(r, *, include_target: bool = False) -> dict:
    """Serialize a Run ORM object to a plain dict.

    Parameters
    ----------
    r:
        A ``Run`` ORM instance.
    include_target:
        When *True*, add a nested ``"target"`` key with the serialized
        target configuration (requires ``r.target_config`` to be loaded).
    """
    d: dict = {
        "id": r.id,
        "run_group_id": r.run_group_id,
        "evaluation_version_id": r.evaluation_version_id,
        "target_config_id": r.target_config_id,
        "machine_snapshot_id": r.machine_snapshot_id,
        "dataset_version_id": r.dataset_version_id,
        "status": r.status,
        "trigger_type": r.trigger_type,
        "priority": r.priority,
        "started_at": r.started_at,
        "scoring_started_at": r.scoring_started_at,
        "completed_at": r.completed_at,
        "error_message": r.error_message,
        "total_items": r.total_items,
        "completed_items": r.completed_items,
        "failed_items": r.failed_items,
        "skipped_items": r.skipped_items,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }
    if include_target and hasattr(r, "target_config") and r.target_config is not None:
        d["target"] = target_to_dict(r.target_config)
    return d


def target_to_dict(t) -> dict:
    """Serialize a TargetConfiguration ORM object to a plain dict.

    Sensitive keys inside ``runtime_options`` are automatically redacted.
    """
    return {
        "id": t.id,
        "name": t.name,
        "model_name": t.model_name,
        "model_family": t.model_family,
        "provider": t.provider,
        "endpoint_url": t.endpoint_url,
        "machine_profile_id": t.machine_profile_id,
        "runtime_backend": t.runtime_backend,
        "prompt_wrapper": t.prompt_wrapper,
        "inference_params": json.loads(t.inference_params) if t.inference_params else None,
        "runtime_options": (
            _redact_keys(json.loads(t.runtime_options)) if t.runtime_options else None
        ),
        "tags": json.loads(t.tags) if t.tags else None,
        "notes": t.notes,
        "is_archived": t.is_archived,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }
