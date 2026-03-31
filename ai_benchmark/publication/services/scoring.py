"""Candidate scoring: compute editorial rank for publication candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..types import CandidateItem, ScoredCandidate

if TYPE_CHECKING:
    from ..config import PublicationSettings

# Default scoring weights. Sum to 1.0.
_WEIGHTS = {
    "verification": 0.25,
    "confidence": 0.20,
    "source_diversity": 0.15,
    "recency": 0.10,
    "cross_ref_density": 0.10,
    "novelty": 0.10,
    "benchmark_magnitude": 0.05,
    "anomaly_signal": 0.05,
}

# Verification status scores (0–1 range).
_VERIFICATION_SCORES = {
    "confirmed": 1.0,
    "unconfirmed": 0.4,
    "conflicted": 0.1,
}

# Confidence tier scores (0–1 range).
_CONFIDENCE_SCORES = {
    "official_self_report": 1.0,
    "benchmark_owner_report": 0.9,
    "high_secondary": 0.7,
    "medium_discovery": 0.4,
    "low_discovery": 0.15,
}


async def score_candidates(
    candidates: list[CandidateItem],
    settings: PublicationSettings,
) -> list[ScoredCandidate]:
    """Score candidates and return sorted list (highest score first).

    Scoring is deterministic: same input produces same output.
    """
    now = datetime.now(UTC)
    scored: list[ScoredCandidate] = []

    for candidate in candidates:
        breakdown = _compute_breakdown(candidate, now)
        total = sum(_WEIGHTS[k] * breakdown[k] for k in _WEIGHTS)
        scored.append(
            ScoredCandidate(
                candidate=candidate,
                score=round(total, 4),
                score_breakdown=breakdown,
            )
        )

    # Deterministic sort: score descending, then observed_at ascending for ties
    scored.sort(key=lambda s: (-s.score, s.candidate.observed_at))
    return scored


def _compute_breakdown(candidate: CandidateItem, now: datetime) -> dict[str, float]:
    """Compute individual scoring factors for a candidate."""
    return {
        "verification": _VERIFICATION_SCORES.get(candidate.verification_status, 0.0),
        "confidence": _CONFIDENCE_SCORES.get(candidate.confidence_tier, 0.0),
        "source_diversity": _score_source_diversity(candidate.source_count),
        "recency": _score_recency(candidate.observed_at, now),
        "cross_ref_density": _score_cross_refs(candidate.cross_ref_count),
        "novelty": _score_novelty(candidate),
        "benchmark_magnitude": _score_benchmark(candidate),
        "anomaly_signal": _score_anomaly(candidate.analysis_signals),
    }


def _score_source_diversity(source_count: int) -> float:
    """More independent sources = higher score. Caps at 5."""
    return min(source_count / 5.0, 1.0)


def _score_recency(observed_at: str, now: datetime) -> float:
    """More recent = higher score. Linear decay over 48 hours."""
    if not observed_at:
        return 0.0
    try:
        obs = datetime.fromisoformat(observed_at)
        if obs.tzinfo is None:
            obs = obs.replace(tzinfo=UTC)
        age_hours = (now - obs).total_seconds() / 3600
        return max(0.0, 1.0 - age_hours / 48.0)
    except (ValueError, TypeError):
        return 0.0


def _score_cross_refs(count: int) -> float:
    """More cross-references = higher score. Caps at 5."""
    return min(count / 5.0, 1.0)


def _score_novelty(candidate: CandidateItem) -> float:
    """New model families and first-time events score higher."""
    signals = candidate.analysis_signals
    insight_types = signals.get("insight_types", [])
    if "new_model_families" in insight_types or "new_org" in insight_types:
        return 1.0
    # Model releases and benchmark records are inherently novel
    if candidate.event_type in ("model_release", "benchmark_result"):
        return 0.6
    return 0.3


def _score_benchmark(candidate: CandidateItem) -> float:
    """Benchmark-related items with content get a boost."""
    if candidate.benchmark_name and candidate.raw_content:
        return 0.8
    if candidate.benchmark_name:
        return 0.4
    return 0.0


def _score_anomaly(signals: dict) -> float:
    """Anomaly/spotlight signals from analysis pipeline."""
    if not signals:
        return 0.0
    severity = signals.get("max_severity", "")
    return {"critical": 1.0, "notable": 0.6, "info": 0.2}.get(severity, 0.0)
