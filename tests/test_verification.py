"""Tests for verification hierarchy and claim management."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.processing.verification import (
    check_confirmation,
    create_claim,
    detect_claim_conflict,
    update_confirmation_status,
)


def _make_event(session, **kwargs) -> EventRecord:
    defaults = {
        "source_id": 1,
        "title": "Test Event",
        "normalized_title": "test event",
        "organization": "OpenAI",
        "source_type": "changelog",
        "canonical_path": "/changelog",
        "event_type": "model_release",
        "observed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    event = EventRecord(**defaults)
    session.add(event)
    return event


@pytest.mark.asyncio
async def test_create_claim(db_session):
    event = _make_event(db_session)
    await db_session.flush()

    claim = await create_claim(
        db_session,
        event=event,
        claim_text="GPT-5 released with 1M context",
        source_type="changelog",
        source_name="OpenAI",
        confidence_tier="official_self_report",
    )
    assert claim.id is not None
    assert claim.event_id == event.id
    assert claim.confirmation_status == "unconfirmed"


@pytest.mark.asyncio
async def test_create_claim_without_event(db_session):
    claim = await create_claim(
        db_session,
        event=None,
        claim_text="Rumored GPT-5 release",
        source_type="news",
        source_name="TechCrunch",
        confidence_tier="news_discovery",
    )
    assert claim.event_id is None


@pytest.mark.asyncio
async def test_model_release_confirmed_with_2_official(db_session):
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    await create_claim(
        db_session, event, "GPT-5 on launch page",
        "launch_page", "OpenAI", "official_self_report",
    )
    await create_claim(
        db_session, event, "GPT-5 in model catalog",
        "model_catalog", "OpenAI", "official_self_report",
    )

    assert await check_confirmation(db_session, event) is True


@pytest.mark.asyncio
async def test_model_release_not_confirmed_with_1_official(db_session):
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    await create_claim(
        db_session, event, "GPT-5 on launch page",
        "launch_page", "OpenAI", "official_self_report",
    )

    assert await check_confirmation(db_session, event) is False


@pytest.mark.asyncio
async def test_benchmark_confirmed_with_owner(db_session):
    event = _make_event(db_session, event_type="benchmark_result")
    await db_session.flush()

    await create_claim(
        db_session, event, "Model X scores 95% on SWE-bench",
        "leaderboard", "SWE-bench", "benchmark_owner_report",
    )

    assert await check_confirmation(db_session, event) is True


@pytest.mark.asyncio
async def test_benchmark_not_confirmed_without_owner(db_session):
    event = _make_event(db_session, event_type="benchmark_result")
    await db_session.flush()

    await create_claim(
        db_session, event, "Model X claims 95% on SWE-bench",
        "blog", "OpenAI", "official_self_report",
    )

    assert await check_confirmation(db_session, event) is False


@pytest.mark.asyncio
async def test_pricing_confirmed_with_pricing_page(db_session):
    event = _make_event(db_session, event_type="pricing_change")
    await db_session.flush()

    await create_claim(
        db_session, event, "New pricing: $5/1M tokens",
        "pricing_page", "OpenAI", "official_self_report",
    )

    assert await check_confirmation(db_session, event) is True


@pytest.mark.asyncio
async def test_pricing_not_confirmed_from_blog(db_session):
    event = _make_event(db_session, event_type="pricing_change")
    await db_session.flush()

    await create_claim(
        db_session, event, "Pricing rumored to change",
        "blog", "TechCrunch", "news_discovery",
    )

    assert await check_confirmation(db_session, event) is False


@pytest.mark.asyncio
async def test_update_confirmation_status_confirmed(db_session):
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    await create_claim(
        db_session, event, "GPT-5 on launch page",
        "launch_page", "OpenAI", "official_self_report",
    )
    await create_claim(
        db_session, event, "GPT-5 in docs",
        "developer_docs", "OpenAI", "official_self_report",
    )

    status = await update_confirmation_status(db_session, event)
    assert status == "confirmed"


@pytest.mark.asyncio
async def test_update_confirmation_status_unconfirmed(db_session):
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    status = await update_confirmation_status(db_session, event)
    assert status == "unconfirmed"


@pytest.mark.asyncio
async def test_claims_never_merged(db_session):
    """Separate claims from different sources must remain as distinct records."""
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    claim1 = await create_claim(
        db_session, event, "GPT-5 released March 28",
        "newsroom", "OpenAI", "official_self_report",
    )
    claim2 = await create_claim(
        db_session, event, "GPT-5 available in API",
        "changelog", "OpenAI", "official_self_report",
    )
    claim3 = await create_claim(
        db_session, event, "OpenAI launches GPT-5",
        "news", "Reuters", "reputable_news_report",
    )

    assert claim1.id != claim2.id != claim3.id
    assert claim1.source_type != claim2.source_type
    assert claim1.confidence_tier != claim3.confidence_tier


@pytest.mark.asyncio
async def test_model_release_confirmed_chain_ordering(db_session):
    """Model release confirmed when 2+ chain source types with one in top 3."""
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    # launch_page is rank 1 (top 3), developer_docs is rank 2
    await create_claim(
        db_session, event, "GPT-5 on launch page",
        "launch_page", "OpenAI", "official_self_report",
    )
    await create_claim(
        db_session, event, "GPT-5 in developer docs",
        "developer_docs", "OpenAI", "official_self_report",
    )
    assert await check_confirmation(db_session, event) is True


@pytest.mark.asyncio
async def test_model_release_not_confirmed_low_rank_only(db_session):
    """Model release NOT confirmed when claims are only from low-rank source types."""
    event = _make_event(db_session, event_type="model_release")
    await db_session.flush()

    # system_card is rank 7, release_notes is rank 6 — neither in top 3
    await create_claim(
        db_session, event, "GPT-5 in system card",
        "system_card", "OpenAI", "official_self_report",
    )
    await create_claim(
        db_session, event, "GPT-5 in release notes",
        "release_notes", "OpenAI", "official_self_report",
    )
    assert await check_confirmation(db_session, event) is False


@pytest.mark.asyncio
async def test_conflict_detection_numerical_disagreement(db_session):
    """Claims with >10% numerical disagreement are flagged as conflicted."""
    event = _make_event(db_session, event_type="benchmark_result")
    await db_session.flush()

    await create_claim(
        db_session, event, "Model X scores 95% on SWE-bench",
        "leaderboard", "SWE-bench", "benchmark_owner_report",
    )
    await create_claim(
        db_session, event, "Model X scores 80% on SWE-bench",
        "blog", "OpenAI", "official_self_report",
    )

    status = await update_confirmation_status(db_session, event)
    assert status == "conflicted"


def test_detect_claim_conflict_true():
    """detect_claim_conflict returns True for >10% numerical disagreement."""
    a = ClaimRecord(claim_text="Score: 95%", source_type="a", source_name="A", confidence_tier="x")
    b = ClaimRecord(claim_text="Score: 80%", source_type="b", source_name="B", confidence_tier="x")
    assert detect_claim_conflict(a, b) is True


def test_detect_claim_conflict_false():
    """detect_claim_conflict returns False for <10% numerical disagreement."""
    a = ClaimRecord(claim_text="Score: 95%", source_type="a", source_name="A", confidence_tier="x")
    b = ClaimRecord(claim_text="Score: 94%", source_type="b", source_name="B", confidence_tier="x")
    assert detect_claim_conflict(a, b) is False


@pytest.mark.asyncio
async def test_page_title_propagated_to_claim(db_session):
    """page_title from RawItem propagates through to ClaimRecord."""
    event = _make_event(db_session)
    await db_session.flush()

    claim = await create_claim(
        db_session, event, "Test claim",
        "changelog", "OpenAI", "official_self_report",
        page_title="Model changelog",
    )
    assert claim.page_title == "Model changelog"
