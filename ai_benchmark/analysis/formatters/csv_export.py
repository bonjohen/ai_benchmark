"""CSV serialization for analysis results."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AnalysisInsight
    from ..types import (
        CorrelationMatrix,
        EvolutionSummary,
        Leaderboard,
        ModelSummary,
        SpotlightReport,
        VerificationReport,
    )


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


def spotlight_to_csv(report: SpotlightReport) -> str:
    """Serialize spotlight report to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "model_slug",
            "organization",
            "first_seen",
            "status",
            "debut_strength",
            "benchmark_count",
            "xref_count",
        ]
    )
    for e in report.entries:
        writer.writerow(
            [
                e.model_slug,
                e.organization,
                e.first_seen,
                e.status,
                e.debut_strength,
                e.benchmark_count,
                e.xref_count,
            ]
        )
    return output.getvalue()


def evolution_to_csv(summaries: list[EvolutionSummary]) -> str:
    """Serialize evolution summaries to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "benchmark_name",
            "current_leader",
            "current_top_score",
            "total_improvement",
            "improvement_rate_per_month",
            "saturation_pct",
            "models_evaluated",
            "last_record_date",
        ]
    )
    for s in summaries:
        writer.writerow(
            [
                s.benchmark_name,
                s.current_leader or "",
                s.current_top_score if s.current_top_score is not None else "",
                s.total_improvement if s.total_improvement is not None else "",
                s.improvement_rate_per_month if s.improvement_rate_per_month is not None else "",
                s.saturation_pct if s.saturation_pct is not None else "",
                s.models_evaluated,
                s.last_record_date or "",
            ]
        )
    return output.getvalue()


def verification_to_csv(report: VerificationReport) -> str:
    """Serialize verification report model summaries to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "model_slug",
            "organization",
            "total_claims",
            "confirmed_pct",
            "conflicted_pct",
            "source_count",
            "highest_confidence_tier",
            "xref_confirms_count",
        ]
    )
    for m in report.model_verifications:
        writer.writerow(
            [
                m.model_slug,
                m.organization,
                m.total_claims,
                m.confirmed_pct,
                m.conflicted_pct,
                m.source_count,
                m.highest_confidence_tier,
                m.xref_confirms_count,
            ]
        )
    return output.getvalue()


def correlation_to_csv(matrix: CorrelationMatrix) -> str:
    """Serialize correlation matrix to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["benchmark_a", "benchmark_b", "correlation", "overlap_count", "label"])
    for e in matrix.entries:
        writer.writerow([e.benchmark_a, e.benchmark_b, e.correlation, e.overlap_count, e.label])
    return output.getvalue()
