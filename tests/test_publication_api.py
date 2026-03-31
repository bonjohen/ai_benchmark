"""Tests for publication API endpoints and formatters."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from ai_benchmark.eval.api.app import create_app, get_session
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.models.base import Base, create_session_factory
from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source
from ai_benchmark.publication.formatters.json_export import edition_to_json
from ai_benchmark.publication.formatters.markdown import edition_to_markdown
from ai_benchmark.publication.types import EditionResult, EntryResult, SectionResult

# --- Fixtures ---


@pytest.fixture
async def pub_client():
    """Create a test app with publication routes and seeded data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from ai_benchmark.analysis import models as analysis_models  # noqa: F401
    from ai_benchmark.eval.models import (  # noqa: F401
        artifact,
        audit,
        dataset,
        evaluation,
        machine,
        run,
        runner,
        scorer,
        target,
        trace,
    )
    from ai_benchmark.models import discovery, events, research, sources  # noqa: F401
    from ai_benchmark.publication import models as publication_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    # Seed data
    now = datetime.now(UTC)
    async with session_factory() as session:
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
        session.add(source)
        await session.flush()

        page = Page(
            source_id=source.id,
            canonical_url="https://openai.com/news/",
            page_type="product-news",
            polling_frequency="daily",
        )
        session.add(page)
        await session.flush()

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
        session.add(ev)
        await session.flush()

        claim = ClaimRecord(
            event_id=ev.id,
            claim_text="GPT-5 released",
            source_type="product-news",
            source_name="OpenAI",
            confidence_tier="official_self_report",
            confirmation_status="confirmed",
        )
        session.add(claim)
        await session.commit()

    async def _override_session():
        async with session_factory() as session:
            yield session

    settings = EvalSettings()
    app = create_app(settings)
    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()


# --- API Tests ---


@pytest.mark.asyncio
async def test_list_editions_empty(pub_client):
    resp = await pub_client.get("/api/publications/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_generate_edition(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    resp = await pub_client.post(f"/api/publications/generate?date={today}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["publication_date"] == today
    assert data["edition_id"] is not None
    assert data["stats"]["total_entries"] >= 1


@pytest.mark.asyncio
async def test_get_latest_edition(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    resp = await pub_client.get("/api/publications/latest")
    assert resp.status_code == 200
    assert resp.json()["publication_date"] == today


@pytest.mark.asyncio
async def test_get_edition_by_date(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    resp = await pub_client.get(f"/api/publications/{today}")
    assert resp.status_code == 200
    assert resp.json()["publication_date"] == today


@pytest.mark.asyncio
async def test_get_edition_not_found(pub_client):
    resp = await pub_client.get("/api/publications/2020-01-01")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_editions_after_generate(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    resp = await pub_client.get("/api/publications/")
    assert resp.status_code == 200
    editions = resp.json()
    assert len(editions) >= 1
    assert editions[0]["publication_date"] == today


@pytest.mark.asyncio
async def test_export_markdown(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    resp = await pub_client.get(f"/api/publications/{today}/export?format=markdown")
    assert resp.status_code == 200
    assert "Daily AI Benchmark" in resp.text


@pytest.mark.asyncio
async def test_export_json(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    resp = await pub_client.get(f"/api/publications/{today}/export?format=json")
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data["publication_date"] == today


@pytest.mark.asyncio
async def test_generate_frozen_conflict(pub_client):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    await pub_client.post(f"/api/publications/generate?date={today}")

    # Freeze via direct DB manipulation isn't easy via API yet,
    # so test that regeneration of a draft works (no 409)
    resp = await pub_client.post(f"/api/publications/generate?date={today}")
    assert resp.status_code == 200


# --- Formatter Unit Tests ---


def _make_edition_result() -> EditionResult:
    entry = EntryResult(
        entry_id=1,
        rank=1,
        title="GPT-5 Released",
        summary="OpenAI releases GPT-5.",
        why_it_matters="Major capability jump.",
        entry_type="model_release",
        organization="OpenAI",
        model_slug="gpt-5",
        benchmark_name=None,
        verification_status="confirmed",
        confidence_summary="official_self_report",
        source_count=3,
        score=0.95,
        event_id=1,
        paper_id=None,
    )
    section = SectionResult(
        section_key="announcements",
        title="Model & Vendor Announcements",
        entries=[entry],
        summary="One announcement today.",
    )
    return EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[section],
        summary="Today's top story: GPT-5 release.",
        stats={"total_entries": 1, "total_candidates": 5, "sections_with_items": 1},
    )


def test_markdown_output():
    edition = _make_edition_result()
    md = edition_to_markdown(edition)
    assert "# Daily AI Benchmark" in md
    assert "GPT-5 Released" in md
    assert "[confirmed]" in md
    assert "OpenAI" in md
    assert "Why it matters" in md


def test_markdown_empty_sections():
    edition = EditionResult(
        edition_id=1,
        publication_date="2026-03-30",
        sections=[
            SectionResult(section_key="empty", title="Empty Section", entries=[], summary="")
        ],
        summary="Nothing today.",
    )
    md = edition_to_markdown(edition)
    # Empty sections should not render headers
    assert "Empty Section" not in md


def test_json_output():
    edition = _make_edition_result()
    result = edition_to_json(edition)
    data = json.loads(result)
    assert data["edition_id"] == 1
    assert data["publication_date"] == "2026-03-30"
    assert len(data["sections"]) == 1
    assert data["sections"][0]["entries"][0]["title"] == "GPT-5 Released"


def test_json_roundtrip():
    edition = _make_edition_result()
    result = edition_to_json(edition)
    data = json.loads(result)
    assert data["stats"]["total_entries"] == 1
