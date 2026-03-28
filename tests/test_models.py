"""Smoke tests for data model creation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ai_benchmark.models.events import ClaimRecord, CrossReference, EventRecord
from ai_benchmark.models.research import CandidatePaper, EnrichedPaper
from ai_benchmark.models.sources import Page, Snapshot, Source


@pytest.mark.asyncio
async def test_create_source(db_session):
    source = Source(
        source_name="TestSource",
        category="test",
        organization="TestOrg",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=4.0,
        source_role="test source",
        classification="primary",
    )
    db_session.add(source)
    await db_session.commit()

    result = await db_session.execute(select(Source))
    sources = result.scalars().all()
    assert len(sources) == 1
    assert sources[0].source_name == "TestSource"


@pytest.mark.asyncio
async def test_create_event_record(db_session):
    source = Source(
        source_name="TestSource",
        category="test",
        organization="TestOrg",
        homepage_url="https://example.com",
        base_domain="example.com",
        trust_rating=4.0,
        source_role="test",
        classification="primary",
    )
    db_session.add(source)
    await db_session.commit()

    event = EventRecord(
        source_id=source.id,
        title="GPT-5 Released",
        normalized_title="gpt-5 released",
        organization="OpenAI",
        source_type="official company source",
        canonical_path="/news/gpt-5",
        published_date="2026-03-28",
        event_type="model_release",
        model_slug="gpt-5",
    )
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(EventRecord))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].model_slug == "gpt-5"


@pytest.mark.asyncio
async def test_create_candidate_paper(db_session):
    paper = CandidatePaper(
        title="A New Benchmark for LLMs",
        arxiv_id="2603.12345",
        discovered_via="arxiv",
        status="pending",
    )
    db_session.add(paper)
    await db_session.commit()

    result = await db_session.execute(select(CandidatePaper))
    papers = result.scalars().all()
    assert len(papers) == 1
    assert papers[0].status == "pending"
