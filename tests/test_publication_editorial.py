"""Tests for editorial controls, audit logging, and editorial API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.config import PublicationSettings
from ai_benchmark.publication.models import (
    PublicationAuditLog,
    PublicationEntry,
)
from ai_benchmark.publication.services.edition import generate_edition
from ai_benchmark.publication.services.editorial import (
    freeze_edition,
    override_entry,
    pin_entry,
    restore_entry,
    suppress_entry,
)


def _make_settings(**overrides) -> PublicationSettings:
    defaults = {"_env_file": None, "cutoff_hour": 23}
    defaults.update(overrides)
    return PublicationSettings(**defaults)  # type: ignore[call-arg]


@pytest.fixture
async def edition_with_entry(db_session):
    """Create and generate an edition with at least one entry."""
    now = datetime.now(UTC)
    source = Source(
        source_name="OpenAI",
        category="official",
        organization="OpenAI",
        homepage_url="https://openai.com/",
        base_domain="openai.com",
        trust_rating=5.0,
        source_role="primary",
        classification="primary",
        collection_method="html",
    )
    db_session.add(source)
    await db_session.flush()

    page = Page(
        source_id=source.id,
        canonical_url="https://openai.com/news/",
        page_type="product-news",
        polling_frequency="daily",
    )
    db_session.add(page)
    await db_session.flush()

    ev = EventRecord(
        source_id=source.id,
        page_id=page.id,
        title="GPT-5 Released",
        normalized_title="gpt-5 released",
        organization="OpenAI",
        source_type="product-news",
        canonical_path="https://openai.com/news/gpt-5",
        event_type="model_release",
        model_slug="gpt-5",
        observed_at=now - timedelta(hours=3),
    )
    db_session.add(ev)
    await db_session.flush()

    claim = ClaimRecord(
        event_id=ev.id,
        claim_text="GPT-5 released",
        source_type="product-news",
        source_name="OpenAI",
        confidence_tier="official_self_report",
        confirmation_status="confirmed",
    )
    db_session.add(claim)
    await db_session.flush()

    settings = _make_settings()
    today = now.strftime("%Y-%m-%d")
    result = await generate_edition(db_session, publication_date=today, settings=settings)
    await db_session.flush()

    # Get the first entry
    ent_result = await db_session.execute(
        select(PublicationEntry).where(PublicationEntry.edition_id == result.edition_id).limit(1)
    )
    entry = ent_result.scalar_one()

    return {"edition_id": result.edition_id, "entry_id": entry.id, "date": today}


# --- Pin Tests ---


@pytest.mark.asyncio
async def test_pin_entry(db_session, edition_with_entry):
    data = edition_with_entry
    entry = await pin_entry(db_session, data["entry_id"], "admin")
    assert entry.is_pinned is True

    # Audit log created
    logs = (
        (
            await db_session.execute(
                select(PublicationAuditLog).where(
                    PublicationAuditLog.entry_id == data["entry_id"],
                    PublicationAuditLog.action_type == "pin",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].actor == "admin"


# --- Suppress Tests ---


@pytest.mark.asyncio
async def test_suppress_entry(db_session, edition_with_entry):
    data = edition_with_entry
    entry = await suppress_entry(db_session, data["entry_id"], "editor")
    assert entry.is_suppressed is True
    assert entry.status == "suppressed"


# --- Override Tests ---


@pytest.mark.asyncio
async def test_override_entry(db_session, edition_with_entry):
    data = edition_with_entry
    entry = await override_entry(
        db_session,
        data["entry_id"],
        actor="editor",
        title="Custom Title",
        summary="Custom summary.",
    )
    assert entry.title_final == "Custom Title"
    assert entry.summary_final == "Custom summary."
    assert entry.is_overridden is True
    # Generated text preserved
    assert entry.title_generated != "Custom Title"


# --- Freeze Tests ---


@pytest.mark.asyncio
async def test_freeze_edition(db_session, edition_with_entry):
    data = edition_with_entry
    edition = await freeze_edition(db_session, data["edition_id"], "admin")
    assert edition.status == "frozen"
    assert edition.frozen_at is not None


@pytest.mark.asyncio
async def test_freeze_already_frozen(db_session, edition_with_entry):
    data = edition_with_entry
    await freeze_edition(db_session, data["edition_id"], "admin")
    with pytest.raises(ValueError, match="already frozen"):
        await freeze_edition(db_session, data["edition_id"], "admin")


# --- Restore Tests ---


@pytest.mark.asyncio
async def test_restore_entry(db_session, edition_with_entry):
    data = edition_with_entry

    # Override first
    await override_entry(
        db_session,
        data["entry_id"],
        actor="editor",
        title="Custom Title",
    )
    entry = await db_session.get(PublicationEntry, data["entry_id"])
    assert entry.title_final == "Custom Title"
    assert entry.is_overridden is True

    # Restore
    restored = await restore_entry(db_session, data["entry_id"], "editor")
    assert restored.title_final == restored.title_generated
    assert restored.is_overridden is False
    assert restored.status == "active"


# --- Audit Log Tests ---


@pytest.mark.asyncio
async def test_audit_log_records_all_actions(db_session, edition_with_entry):
    data = edition_with_entry
    await pin_entry(db_session, data["entry_id"], "admin")
    await suppress_entry(db_session, data["entry_id"], "editor")
    await restore_entry(db_session, data["entry_id"], "admin")
    await freeze_edition(db_session, data["edition_id"], "admin")

    logs = (
        (
            await db_session.execute(
                select(PublicationAuditLog).where(
                    PublicationAuditLog.edition_id == data["edition_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    action_types = {log.action_type for log in logs}
    assert "pin" in action_types
    assert "suppress" in action_types
    assert "restore" in action_types
    assert "freeze" in action_types


@pytest.mark.asyncio
async def test_audit_log_has_before_after(db_session, edition_with_entry):
    data = edition_with_entry
    await pin_entry(db_session, data["entry_id"], "admin")

    log = (
        await db_session.execute(
            select(PublicationAuditLog).where(PublicationAuditLog.action_type == "pin")
        )
    ).scalar_one()
    assert log.before_state_json is not None
    assert log.after_state_json is not None
    import json

    before = json.loads(log.before_state_json)
    after = json.loads(log.after_state_json)
    assert before["is_pinned"] is False
    assert after["is_pinned"] is True


# --- Entry Not Found ---


@pytest.mark.asyncio
async def test_pin_entry_not_found(db_session):
    with pytest.raises(ValueError, match="not found"):
        await pin_entry(db_session, 99999, "admin")
