"""Result dataclasses for publication services. Pure data containers, no DB dependency."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateItem:
    """A candidate item eligible for inclusion in a daily edition."""

    event_id: int | None
    paper_id: int | None
    title: str
    organization: str | None
    model_slug: str | None
    benchmark_name: str | None
    event_type: str
    verification_status: str  # confirmed, unconfirmed, conflicted
    confidence_tier: str  # official_self_report, benchmark_owner_report, etc.
    source_count: int
    cross_ref_count: int
    observed_at: str
    raw_content: str | None
    analysis_signals: dict = field(default_factory=dict)


@dataclass
class ScoredCandidate:
    """A candidate with computed editorial score and section assignment."""

    candidate: CandidateItem
    score: float
    score_breakdown: dict = field(default_factory=dict)
    section_key: str = ""


@dataclass
class EntryResult:
    """A rendered publication entry for output."""

    entry_id: int
    rank: int
    title: str
    summary: str
    why_it_matters: str | None
    entry_type: str
    organization: str | None
    model_slug: str | None
    benchmark_name: str | None
    verification_status: str
    confidence_summary: str | None
    source_count: int
    score: float
    event_id: int | None
    paper_id: int | None
    source_links: list[str] = field(default_factory=list)


@dataclass
class SectionResult:
    """A rendered publication section for output."""

    section_key: str
    title: str
    entries: list[EntryResult] = field(default_factory=list)
    summary: str = ""


@dataclass
class EditionResult:
    """A complete rendered daily edition for output."""

    edition_id: int
    publication_date: str
    sections: list[SectionResult] = field(default_factory=list)
    summary: str = ""
    stats: dict = field(default_factory=dict)
