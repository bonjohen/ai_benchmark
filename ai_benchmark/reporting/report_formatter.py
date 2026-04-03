"""JSON formatter for the daily intelligence report."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .report_queries import DailyReport


def format_json(data: DailyReport) -> str:
    """Render the daily report as compact JSON for Claude CLI consumption."""
    return json.dumps(
        {
            "date": data.generated_at.strftime("%Y-%m-%d"),
            "article_count": len(data.articles),
            "articles": [asdict(a) for a in data.articles],
        },
        indent=2,
    )
