"""FastAPI router for the publication pipeline."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _get_session_dep():
    """Import the eval app's get_session dependency."""
    from ..eval.api.app import get_session

    return get_session


_session = Depends(_get_session_dep())


def _to_dict(obj):
    """Convert a dataclass or list of dataclasses to a JSON-serializable dict."""
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


@router.get("/latest")
async def get_latest_edition(
    session: AsyncSession = _session,  # noqa: B008
):
    """Get the most recent publication edition."""

    edition_result = await _load_latest_edition(session)
    if edition_result is None:
        raise HTTPException(status_code=404, detail="No editions found")
    return _to_dict(edition_result)


@router.get("/{date}")
async def get_edition_by_date(
    date: str,
    session: AsyncSession = _session,  # noqa: B008
):
    """Get a publication edition by date (YYYY-MM-DD)."""
    edition_result = await _load_edition_by_date(session, date)
    if edition_result is None:
        raise HTTPException(status_code=404, detail=f"No edition found for {date}")
    return _to_dict(edition_result)


@router.get("/")
async def list_editions(
    limit: int = Query(30, ge=1, le=365),
    status: str | None = Query(None, description="Filter by status"),
    session: AsyncSession = _session,  # noqa: B008
):
    """List publication editions."""
    from sqlalchemy import select

    from .models import PublicationEdition

    stmt = (
        select(PublicationEdition).order_by(PublicationEdition.publication_date.desc()).limit(limit)
    )
    if status:
        stmt = stmt.where(PublicationEdition.status == status)

    result = await session.execute(stmt)
    editions = result.scalars().all()

    return [
        {
            "edition_id": e.id,
            "publication_date": e.publication_date,
            "status": e.status,
            "generated_at": str(e.generated_at) if e.generated_at else None,
            "frozen_at": str(e.frozen_at) if e.frozen_at else None,
            "generation_version": e.generation_version,
        }
        for e in editions
    ]


@router.post("/generate")
async def generate_edition_endpoint(
    date: str = Query(..., description="Publication date (YYYY-MM-DD)"),
    session: AsyncSession = _session,  # noqa: B008
):
    """Generate a publication edition for the given date."""
    from .config import PublicationSettings
    from .services.edition import generate_edition

    settings = PublicationSettings()
    try:
        result = await generate_edition(session, publication_date=date, settings=settings)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    await session.commit()
    return _to_dict(result)


@router.get("/{date}/export")
async def export_edition(
    date: str,
    format: str = Query("json", description="Export format: markdown, json"),
    session: AsyncSession = _session,  # noqa: B008
):
    """Export an edition in the specified format."""
    edition_result = await _load_edition_by_date(session, date)
    if edition_result is None:
        raise HTTPException(status_code=404, detail=f"No edition found for {date}")

    if format == "markdown":
        from .formatters.markdown import edition_to_markdown

        content = edition_to_markdown(edition_result)
        return PlainTextResponse(content, media_type="text/markdown")

    if format == "json":
        from .formatters.json_export import edition_to_json

        content = edition_to_json(edition_result)
        return PlainTextResponse(content, media_type="application/json")

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


# --- Internal helpers ---


async def _load_latest_edition(session: AsyncSession):
    """Load the most recent edition as an EditionResult."""
    from sqlalchemy import select

    from .models import PublicationEdition

    stmt = select(PublicationEdition).order_by(PublicationEdition.publication_date.desc()).limit(1)
    result = await session.execute(stmt)
    edition = result.scalar_one_or_none()
    if edition is None:
        return None
    return await _edition_to_result(session, edition)


async def _load_edition_by_date(session: AsyncSession, date: str):
    """Load an edition by date as an EditionResult."""
    from sqlalchemy import select

    from .models import PublicationEdition

    stmt = select(PublicationEdition).where(PublicationEdition.publication_date == date)
    result = await session.execute(stmt)
    edition = result.scalar_one_or_none()
    if edition is None:
        return None
    return await _edition_to_result(session, edition)


async def _edition_to_result(session: AsyncSession, edition):
    """Convert a DB edition + sections + entries into an EditionResult."""
    import json

    from sqlalchemy import select

    from .models import PublicationEntry, PublicationSection
    from .types import EditionResult, EntryResult, SectionResult

    # Load sections ordered by rank
    sec_stmt = (
        select(PublicationSection)
        .where(PublicationSection.edition_id == edition.id)
        .order_by(PublicationSection.rank)
    )
    sec_result = await session.execute(sec_stmt)
    sections = sec_result.scalars().all()

    section_results: list[SectionResult] = []
    total_entries = 0

    for sec in sections:
        ent_stmt = (
            select(PublicationEntry)
            .where(PublicationEntry.section_id == sec.id)
            .order_by(PublicationEntry.rank)
        )
        ent_result = await session.execute(ent_stmt)
        entries = ent_result.scalars().all()

        entry_results = [
            EntryResult(
                entry_id=e.id,
                rank=e.rank,
                title=e.title_final,
                summary=e.summary_final,
                why_it_matters=e.why_it_matters_final,
                entry_type=e.entry_type,
                organization=e.org_slug,
                model_slug=e.model_slug,
                benchmark_name=e.benchmark_name,
                verification_status=e.verification_status or "",
                confidence_summary=e.confidence_summary,
                source_count=e.source_count,
                score=e.score,
                event_id=e.event_id,
                paper_id=e.paper_id,
            )
            for e in entries
        ]
        total_entries += len(entry_results)

        section_results.append(
            SectionResult(
                section_key=sec.section_key,
                title=sec.title,
                entries=entry_results,
                summary=sec.generated_summary or "",
            )
        )

    stats_json = edition.metadata_json
    stats = json.loads(stats_json) if stats_json else {}

    return EditionResult(
        edition_id=edition.id,
        publication_date=edition.publication_date,
        sections=section_results,
        summary=edition.summary_text or "",
        stats={**stats, "total_entries": total_entries},
    )
