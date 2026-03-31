"""Tests for publication CLI commands."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from click.testing import CliRunner

from ai_benchmark.cli import cli
from ai_benchmark.models.base import Base, create_engine, create_session_factory
from ai_benchmark.models.events import ClaimRecord, EventRecord
from ai_benchmark.models.sources import Page, Source


def _seed_db(db_url: str) -> None:
    """Create tables and seed minimal data."""

    async def _run():
        engine = create_engine(db_url)
        from ai_benchmark.models import discovery, events, research, sources  # noqa: F401
        from ai_benchmark.publication import models as pub_models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        sf = create_session_factory(engine)
        now = datetime.now(UTC)
        async with sf() as session:
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

        await engine.dispose()

    asyncio.run(_run())


def test_cli_generate(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    result = runner.invoke(
        cli,
        ["publish", "generate", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    assert "Edition generated" in result.output
    assert today in result.output


def test_cli_list_no_editions(tmp_path):
    db_path = tmp_path / "test_empty.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["publish", "list"],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    # Before any generate, should show no editions or an empty table
    assert "No editions found" in result.output or "Date" in result.output


def test_cli_list_after_generate(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    runner.invoke(
        cli,
        ["publish", "generate", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    result = runner.invoke(
        cli,
        ["publish", "list"],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    assert today in result.output


def test_cli_status(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    runner.invoke(
        cli,
        ["publish", "generate", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    result = runner.invoke(
        cli,
        ["publish", "status", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    assert "draft" in result.output


def test_cli_export_markdown(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    runner.invoke(
        cli,
        ["publish", "generate", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )

    out_file = tmp_path / "edition.md"
    result = runner.invoke(
        cli,
        ["publish", "export", "--date", today, "--format", "markdown", "--output", str(out_file)],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    assert out_file.exists()
    assert "Daily AI Benchmark" in out_file.read_text(encoding="utf-8")


def test_cli_freeze(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _seed_db(db_url)

    runner = CliRunner()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    runner.invoke(
        cli,
        ["publish", "generate", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    result = runner.invoke(
        cli,
        ["publish", "freeze", "--date", today],
        obj={"settings": _make_settings(db_url)},
    )
    assert result.exit_code == 0
    assert "frozen" in result.output


def _make_settings(db_url: str):
    """Create a PipelineSettings with custom database_url.

    Sets the env var to override .env file loading, since pydantic-settings
    gives env vars higher priority than init values.
    """
    import os

    os.environ["AI_BENCH_DATABASE_URL"] = db_url
    os.environ["AI_BENCH_PUB_DATABASE_URL"] = db_url
    from ai_benchmark.config.settings import PipelineSettings

    return PipelineSettings(_env_file=None)  # type: ignore[call-arg]
