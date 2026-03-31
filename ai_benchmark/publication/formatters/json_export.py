"""JSON export for publication editions."""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EditionResult


def edition_to_json(edition: EditionResult) -> str:
    """Serialize an EditionResult to a JSON string."""
    return json.dumps(dataclasses.asdict(edition), indent=2, default=str)
