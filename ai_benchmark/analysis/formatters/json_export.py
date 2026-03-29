"""JSON serialization for analysis results."""

from __future__ import annotations

import dataclasses
import json
from typing import Any


def to_json(data: Any, indent: int = 2) -> str:
    """Serialize a dataclass, dict, or list to JSON string."""
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        data = dataclasses.asdict(data)
    return json.dumps(data, indent=indent, default=str)
