"""Editorial controls: pin, suppress, override, freeze, regenerate, restore."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..models import PublicationAuditLog, PublicationEdition, PublicationEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..config import PublicationSettings


async def pin_entry(session: AsyncSession, entry_id: int, actor: str) -> PublicationEntry:
    """Pin an entry to the top of its section."""
    entry = await _get_entry(session, entry_id)
    before = _entry_state(entry)
    entry.is_pinned = True
    await _audit(session, entry.edition_id, entry_id, "pin", actor, before, _entry_state(entry))
    await session.flush()
    return entry


async def suppress_entry(session: AsyncSession, entry_id: int, actor: str) -> PublicationEntry:
    """Suppress an entry from the published edition."""
    entry = await _get_entry(session, entry_id)
    before = _entry_state(entry)
    entry.is_suppressed = True
    entry.status = "suppressed"
    await _audit(
        session, entry.edition_id, entry_id, "suppress", actor, before, _entry_state(entry)
    )
    await session.flush()
    return entry


async def override_entry(
    session: AsyncSession,
    entry_id: int,
    *,
    actor: str,
    title: str | None = None,
    summary: str | None = None,
    section_key: str | None = None,
    rank: int | None = None,
) -> PublicationEntry:
    """Override one or more fields on an entry."""
    entry = await _get_entry(session, entry_id)
    _check_not_frozen(session, entry.edition_id)
    before = _entry_state(entry)

    if title is not None:
        entry.title_final = title
    if summary is not None:
        entry.summary_final = summary
    if rank is not None:
        entry.rank = rank
    if any(v is not None for v in (title, summary, section_key, rank)):
        entry.is_overridden = True

    await _audit(
        session, entry.edition_id, entry_id, "override", actor, before, _entry_state(entry)
    )
    await session.flush()
    return entry


async def mark_featured(session: AsyncSession, entry_id: int, actor: str) -> PublicationEntry:
    """Mark an entry as featured (pins and boosts visibility)."""
    entry = await _get_entry(session, entry_id)
    before = _entry_state(entry)
    entry.is_pinned = True
    await _audit(
        session, entry.edition_id, entry_id, "mark_featured", actor, before, _entry_state(entry)
    )
    await session.flush()
    return entry


async def freeze_edition(session: AsyncSession, edition_id: int, actor: str) -> PublicationEdition:
    """Freeze an edition — no further changes allowed."""
    edition = await _get_edition(session, edition_id)
    if edition.status == "frozen":
        msg = f"Edition {edition.publication_date} is already frozen."
        raise ValueError(msg)
    before = {"status": edition.status, "frozen_at": str(edition.frozen_at)}
    edition.status = "frozen"
    edition.frozen_at = datetime.now(UTC)
    after = {"status": edition.status, "frozen_at": str(edition.frozen_at)}
    await _audit(session, edition_id, None, "freeze", actor, before, after)
    await session.flush()
    return edition


async def regenerate_edition(
    session: AsyncSession, edition_id: int, actor: str, settings: PublicationSettings
) -> None:
    """Regenerate a draft or regeneration_available edition."""
    edition = await _get_edition(session, edition_id)
    if edition.status == "frozen":
        msg = f"Edition {edition.publication_date} is frozen and cannot be regenerated."
        raise ValueError(msg)
    await _audit(
        session,
        edition_id,
        None,
        "regenerate",
        actor,
        {"status": edition.status},
        {"status": "regenerating"},
    )

    from .edition import generate_edition

    await generate_edition(session, publication_date=edition.publication_date, settings=settings)
    await session.flush()


async def restore_entry(session: AsyncSession, entry_id: int, actor: str) -> PublicationEntry:
    """Restore an entry to its generated text (undo overrides)."""
    entry = await _get_entry(session, entry_id)
    before = _entry_state(entry)
    entry.title_final = entry.title_generated
    entry.summary_final = entry.summary_generated
    entry.why_it_matters_final = entry.why_it_matters_generated
    entry.is_overridden = False
    entry.is_suppressed = False
    entry.status = "active"
    await _audit(session, entry.edition_id, entry_id, "restore", actor, before, _entry_state(entry))
    await session.flush()
    return entry


# --- Internal helpers ---


async def _get_entry(session: AsyncSession, entry_id: int) -> PublicationEntry:
    entry = await session.get(PublicationEntry, entry_id)
    if entry is None:
        msg = f"Entry {entry_id} not found."
        raise ValueError(msg)
    return entry


async def _get_edition(session: AsyncSession, edition_id: int) -> PublicationEdition:
    edition = await session.get(PublicationEdition, edition_id)
    if edition is None:
        msg = f"Edition {edition_id} not found."
        raise ValueError(msg)
    return edition


def _check_not_frozen(session, edition_id: int) -> None:
    """Check will be done at flush time via DB state. Placeholder for inline use."""


def _entry_state(entry: PublicationEntry) -> dict:
    return {
        "title_final": entry.title_final,
        "summary_final": entry.summary_final,
        "rank": entry.rank,
        "status": entry.status,
        "is_pinned": entry.is_pinned,
        "is_suppressed": entry.is_suppressed,
        "is_overridden": entry.is_overridden,
    }


async def _audit(
    session: AsyncSession,
    edition_id: int,
    entry_id: int | None,
    action_type: str,
    actor: str,
    before: dict,
    after: dict,
) -> None:
    log = PublicationAuditLog(
        edition_id=edition_id,
        entry_id=entry_id,
        action_type=action_type,
        actor=actor,
        before_state_json=json.dumps(before, default=str),
        after_state_json=json.dumps(after, default=str),
    )
    session.add(log)
