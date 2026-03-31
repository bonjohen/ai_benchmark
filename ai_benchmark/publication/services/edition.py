"""Edition generation: orchestrate assembly → scoring → sectioning → rendering → persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..models import PublicationEdition, PublicationEntry, PublicationSection
from ..services.assembly import assemble_candidates
from ..services.render import render_edition_summary, render_entry_text, render_section_summary
from ..services.scoring import score_candidates
from ..services.sectioning import SECTION_DEFS, assign_sections
from ..types import EditionResult, EntryResult, SectionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..config import PublicationSettings


async def generate_edition(
    session: AsyncSession,
    *,
    publication_date: str,
    settings: PublicationSettings,
) -> EditionResult:
    """Generate a complete daily edition for the given date.

    Orchestrates: compute window → assemble → score → section → render → persist.

    Idempotency:
    - If an edition exists for this date and is not frozen, it is deleted and regenerated.
    - If frozen, raises ValueError.
    """
    # Check for existing edition
    existing = await _get_existing_edition(session, publication_date)
    if existing:
        if existing.status == "frozen":
            msg = f"Edition for {publication_date} is frozen and cannot be regenerated."
            raise ValueError(msg)
        # Delete existing draft for regeneration
        await session.delete(existing)
        await session.flush()

    # Compute publication window
    window_start, window_end = _compute_window(publication_date, settings)

    # Assemble candidates
    candidates = await assemble_candidates(
        session,
        window_start=window_start,
        window_end=window_end,
        settings=settings,
    )

    # Score candidates
    scored = await score_candidates(candidates, settings)

    # Assign to sections
    sections_map = await assign_sections(scored, settings)

    # Create edition record
    edition = PublicationEdition(
        publication_date=publication_date,
        window_start=window_start,
        window_end=window_end,
        status="draft",
        generation_version=1,
    )
    session.add(edition)
    await session.flush()

    # Render and persist sections + entries
    section_results: list[SectionResult] = []
    total_entries = 0

    for rank, (section_key, section_title) in enumerate(SECTION_DEFS, 1):
        items = sections_map.get(section_key, [])
        if section_key == "top_summary":
            # Top summary is rendered as edition summary text, not a DB section
            continue

        section_summary = render_section_summary(section_key, items)

        db_section = PublicationSection(
            edition_id=edition.id,
            section_key=section_key,
            title=section_title,
            rank=rank,
            item_count=len(items),
            generated_summary=section_summary,
        )
        session.add(db_section)
        await session.flush()

        entry_results: list[EntryResult] = []
        for entry_rank, sc in enumerate(items, 1):
            text = render_entry_text(sc)

            db_entry = PublicationEntry(
                edition_id=edition.id,
                section_id=db_section.id,
                rank=entry_rank,
                entry_type=sc.candidate.event_type,
                title_generated=text["title"],
                title_final=text["title"],
                summary_generated=text["summary"],
                summary_final=text["summary"],
                why_it_matters_generated=text["why_it_matters"],
                why_it_matters_final=text["why_it_matters"],
                score=sc.score,
                score_explanation_json=json.dumps(sc.score_breakdown),
                event_id=sc.candidate.event_id,
                paper_id=sc.candidate.paper_id,
                benchmark_name=sc.candidate.benchmark_name,
                org_slug=sc.candidate.organization,
                model_slug=sc.candidate.model_slug,
                verification_status=sc.candidate.verification_status,
                confidence_summary=sc.candidate.confidence_tier,
                source_count=sc.candidate.source_count,
            )
            session.add(db_entry)
            await session.flush()

            entry_results.append(
                EntryResult(
                    entry_id=db_entry.id,
                    rank=entry_rank,
                    title=text["title"],
                    summary=text["summary"],
                    why_it_matters=text["why_it_matters"],
                    entry_type=sc.candidate.event_type,
                    organization=sc.candidate.organization,
                    model_slug=sc.candidate.model_slug,
                    benchmark_name=sc.candidate.benchmark_name,
                    verification_status=sc.candidate.verification_status,
                    confidence_summary=sc.candidate.confidence_tier,
                    source_count=sc.candidate.source_count,
                    score=sc.score,
                    event_id=sc.candidate.event_id,
                    paper_id=sc.candidate.paper_id,
                )
            )
            total_entries += 1

        section_results.append(
            SectionResult(
                section_key=section_key,
                title=section_title,
                entries=entry_results,
                summary=section_summary,
            )
        )

    # Render edition summary and update record
    edition_summary = render_edition_summary(sections_map)
    edition.summary_text = edition_summary

    top_headlines = [sc.candidate.title for sc in sections_map.get("top_summary", [])[:3]]
    edition.top_headlines_json = json.dumps(top_headlines)

    await session.flush()

    return EditionResult(
        edition_id=edition.id,
        publication_date=publication_date,
        sections=section_results,
        summary=edition_summary,
        stats={
            "total_entries": total_entries,
            "total_candidates": len(candidates),
            "sections_with_items": sum(1 for s in section_results if s.entries),
        },
    )


async def _get_existing_edition(
    session: AsyncSession, publication_date: str
) -> PublicationEdition | None:
    """Look up an existing edition for the given date."""
    stmt = select(PublicationEdition).where(PublicationEdition.publication_date == publication_date)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _compute_window(
    publication_date: str, settings: PublicationSettings
) -> tuple[datetime, datetime]:
    """Compute the publication window from date string and settings."""
    date = datetime.strptime(publication_date, "%Y-%m-%d").replace(tzinfo=UTC)
    window_end = date.replace(hour=settings.cutoff_hour, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=24)
    return window_start, window_end
