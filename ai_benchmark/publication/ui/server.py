"""Mount Jinja2 templates and static files for the publication UI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ...eval.api.app import get_session  # noqa: B008
from ..api import _load_edition_by_date, _load_latest_edition

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def latest_page(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Daily landing page showing the latest edition."""
    edition = await _load_latest_edition(session)
    return templates.TemplateResponse(
        "latest.html",
        {
            "request": request,
            "edition": edition,
            "active_page": "latest",
        },
    )


@router.get("/archive", response_class=HTMLResponse)
async def archive_page(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Archive page listing prior editions."""
    from sqlalchemy import select

    from ..models import PublicationEdition

    stmt = select(PublicationEdition).order_by(PublicationEdition.publication_date.desc()).limit(90)
    result = await session.execute(stmt)
    editions = result.scalars().all()
    return templates.TemplateResponse(
        "archive.html",
        {
            "request": request,
            "editions": editions,
            "active_page": "archive",
        },
    )


@router.get("/{date}", response_class=HTMLResponse)
async def detail_page(
    date: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Edition detail page."""
    edition = await _load_edition_by_date(session, date)
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "edition": edition,
            "date": date,
            "active_page": "detail",
        },
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """Editorial control page for the latest edition."""
    from sqlalchemy import select

    from ..models import (
        PublicationAuditLog,
        PublicationEdition,
        PublicationEntry,
        PublicationSection,
    )

    # Load latest edition
    stmt = select(PublicationEdition).order_by(PublicationEdition.publication_date.desc()).limit(1)
    result = await session.execute(stmt)
    edition = result.scalar_one_or_none()

    entries = []
    audit_logs = []
    if edition:
        # Load entries with section info
        ent_stmt = (
            select(PublicationEntry, PublicationSection.section_key)
            .join(PublicationSection, PublicationEntry.section_id == PublicationSection.id)
            .where(PublicationEntry.edition_id == edition.id)
            .order_by(PublicationSection.rank, PublicationEntry.rank)
        )
        ent_result = await session.execute(ent_stmt)
        for entry, section_key in ent_result.all():
            entry.section_key = section_key  # type: ignore[attr-defined]
            entries.append(entry)

        # Load audit logs
        log_stmt = (
            select(PublicationAuditLog)
            .where(PublicationAuditLog.edition_id == edition.id)
            .order_by(PublicationAuditLog.created_at.desc())
            .limit(50)
        )
        log_result = await session.execute(log_stmt)
        audit_logs = log_result.scalars().all()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "edition": edition,
            "entries": entries,
            "audit_logs": audit_logs,
            "active_page": "admin",
        },
    )


def mount_publication_ui(app):
    """Mount publication templates and static files on the FastAPI app."""
    app.mount(
        "/publication/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="publication-static",
    )
    app.include_router(router, prefix="/publication")
