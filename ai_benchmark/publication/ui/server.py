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


def mount_publication_ui(app):
    """Mount publication templates and static files on the FastAPI app."""
    app.mount(
        "/publication/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="publication-static",
    )
    app.include_router(router, prefix="/publication")
