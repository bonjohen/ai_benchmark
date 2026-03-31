"""Tests for publication UI routes."""

from __future__ import annotations

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


@pytest.fixture
async def ui_client():
    """Create a test app with publication UI and seeded data."""
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

    # Seed data and generate an edition
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

    # Generate edition
    today = now.strftime("%Y-%m-%d")
    async with session_factory() as session:
        from ai_benchmark.publication.config import PublicationSettings
        from ai_benchmark.publication.services.edition import generate_edition

        pub_settings = PublicationSettings(cutoff_hour=23, _env_file=None)  # type: ignore[call-arg]
        await generate_edition(session, publication_date=today, settings=pub_settings)
        await session.commit()

    async def _override_session():
        async with session_factory() as session:
            yield session

    settings = EvalSettings()
    app = create_app(settings)
    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, today

    await engine.dispose()


@pytest.mark.asyncio
async def test_latest_page(ui_client):
    client, _today = ui_client
    resp = await client.get("/publication/")
    assert resp.status_code == 200
    assert "Daily AI Benchmark" in resp.text
    assert "GPT-5 Released" in resp.text


@pytest.mark.asyncio
async def test_archive_page(ui_client):
    client, today = ui_client
    resp = await client.get("/publication/archive")
    assert resp.status_code == 200
    assert today in resp.text


@pytest.mark.asyncio
async def test_detail_page(ui_client):
    client, today = ui_client
    resp = await client.get(f"/publication/{today}")
    assert resp.status_code == 200
    assert "GPT-5 Released" in resp.text
    assert "Export Markdown" in resp.text


@pytest.mark.asyncio
async def test_detail_page_not_found(ui_client):
    client, _today = ui_client
    resp = await client.get("/publication/2020-01-01")
    assert resp.status_code == 200
    assert "Edition Not Found" in resp.text


@pytest.mark.asyncio
async def test_static_css(ui_client):
    client, _today = ui_client
    resp = await client.get("/publication/static/css/publication.css")
    assert resp.status_code == 200
    assert "pub-nav" in resp.text


@pytest.mark.asyncio
async def test_static_js(ui_client):
    client, _today = ui_client
    resp = await client.get("/publication/static/js/publication.js")
    assert resp.status_code == 200
    assert "toggleDetail" in resp.text
