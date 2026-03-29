"""CSV serialization for analysis results."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AnalysisInsight
    from ..types import Leaderboard, ModelSummary


def models_to_csv(models: list[ModelSummary]) -> str:
    """Serialize model summaries to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["model_slug", "organization", "first_seen", "latest_activity", "event_count", "status"]
    )
    for m in models:
        writer.writerow(
            [m.model_slug, m.organization, m.first_seen, m.latest_activity, m.event_count, m.status]
        )
    return output.getvalue()


def leaderboard_to_csv(leaderboard: Leaderboard) -> str:
    """Serialize a benchmark leaderboard to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["rank", "model_slug", "score", "date", "source_name", "benchmark_variant"])
    for i, entry in enumerate(leaderboard.entries, 1):
        writer.writerow(
            [
                i,
                entry.model_slug,
                entry.score if entry.score is not None else "",
                entry.date,
                entry.source_name,
                entry.benchmark_variant,
            ]
        )
    return output.getvalue()


def insights_to_csv(insights: list[AnalysisInsight]) -> str:
    """Serialize analysis insights to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "insight_type",
            "severity",
            "title",
            "description",
            "related_model_slug",
            "related_org",
            "detected_at",
        ]
    )
    for i in insights:
        writer.writerow(
            [
                i.id,
                i.insight_type,
                i.severity,
                i.title,
                i.description,
                i.related_model_slug or "",
                i.related_org or "",
                i.detected_at.isoformat() if i.detected_at else "",
            ]
        )
    return output.getvalue()
