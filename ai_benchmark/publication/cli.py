"""CLI commands for the publication pipeline."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import click

from ..models.base import Base, create_engine, create_session_factory

if TYPE_CHECKING:
    from ..config.settings import PipelineSettings


def _get_publication_engine(settings: PipelineSettings):
    """Create engine with all models registered."""
    engine = create_engine(settings.database_url)
    from ..analysis import models as analysis_models  # noqa: F401
    from ..models import discovery, events, research, sources  # noqa: F401
    from ..publication import models as publication_models  # noqa: F401

    return engine


@click.group("publish")
def publish_group() -> None:
    """Daily publication pipeline commands."""


@publish_group.command("generate")
@click.option("--date", required=True, help="Publication date (YYYY-MM-DD).")
@click.option("--force", is_flag=True, help="Force regeneration of draft edition.")
@click.pass_context
def generate(ctx: click.Context, date: str, force: bool) -> None:
    """Generate a daily publication edition."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_publication_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .config import PublicationSettings
            from .services.edition import generate_edition

            pub_settings = PublicationSettings()
            result = await generate_edition(session, publication_date=date, settings=pub_settings)
            await session.commit()

            click.echo(f"Edition generated for {date}")
            click.echo(f"  ID: {result.edition_id}")
            click.echo(f"  Entries: {result.stats.get('total_entries', 0)}")
            click.echo(f"  Candidates: {result.stats.get('total_candidates', 0)}")
            click.echo(f"  Sections with items: {result.stats.get('sections_with_items', 0)}")
            click.echo(f"  Summary: {result.summary}")

        await engine.dispose()

    asyncio.run(_run())


@publish_group.command("list")
@click.option("--limit", default=30, help="Maximum editions to show.")
@click.option("--status", default=None, help="Filter by status.")
@click.pass_context
def list_editions(ctx: click.Context, limit: int, status: str | None) -> None:
    """List publication editions."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_publication_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from sqlalchemy import select

            from .models import PublicationEdition

            stmt = (
                select(PublicationEdition)
                .order_by(PublicationEdition.publication_date.desc())
                .limit(limit)
            )
            if status:
                stmt = stmt.where(PublicationEdition.status == status)

            result = await session.execute(stmt)
            editions = result.scalars().all()

            if not editions:
                click.echo("No editions found.")
                return

            click.echo(f"{'Date':<12} {'Status':<12} {'Version':<8} {'Generated At'}")
            click.echo("-" * 60)
            for e in editions:
                gen_at = str(e.generated_at)[:19] if e.generated_at else "—"
                click.echo(
                    f"{e.publication_date:<12} {e.status:<12} {e.generation_version:<8} {gen_at}"
                )

        await engine.dispose()

    asyncio.run(_run())


@publish_group.command("export")
@click.option("--date", required=True, help="Publication date (YYYY-MM-DD).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Export format.",
)
@click.option("--output", "output_file", default=None, help="Output file path.")
@click.pass_context
def export(ctx: click.Context, date: str, output_format: str, output_file: str | None) -> None:
    """Export a publication edition."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_publication_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from .api import _load_edition_by_date

            edition_result = await _load_edition_by_date(session, date)
            if edition_result is None:
                click.echo(f"No edition found for {date}.")
                return

            if output_format == "markdown":
                from .formatters.markdown import edition_to_markdown

                content = edition_to_markdown(edition_result)
            else:
                from .formatters.json_export import edition_to_json

                content = edition_to_json(edition_result)

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)
                click.echo(f"Exported to {output_file}")
            else:
                click.echo(content)

        await engine.dispose()

    asyncio.run(_run())


@publish_group.command("status")
@click.option("--date", default=None, help="Publication date (YYYY-MM-DD). Default: latest.")
@click.pass_context
def status(ctx: click.Context, date: str | None) -> None:
    """Show publication status for a date."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        engine = _get_publication_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from sqlalchemy import func, select

            from .models import PublicationEdition, PublicationEntry, PublicationSection

            if date:
                stmt = select(PublicationEdition).where(PublicationEdition.publication_date == date)
            else:
                stmt = (
                    select(PublicationEdition)
                    .order_by(PublicationEdition.publication_date.desc())
                    .limit(1)
                )
            result = await session.execute(stmt)
            edition = result.scalar_one_or_none()

            if edition is None:
                click.echo("No edition found.")
                return

            click.echo(f"Edition: {edition.publication_date}")
            click.echo(f"  Status: {edition.status}")
            click.echo(f"  Version: {edition.generation_version}")
            click.echo(f"  Generated: {edition.generated_at}")
            click.echo(f"  Frozen: {edition.frozen_at or '—'}")
            click.echo(f"  Summary: {edition.summary_text or '—'}")

            sec_result = await session.execute(
                select(PublicationSection).where(PublicationSection.edition_id == edition.id)
            )
            sections = sec_result.scalars().all()
            for sec in sections:
                ent_count_result = await session.execute(
                    select(func.count(PublicationEntry.id)).where(
                        PublicationEntry.section_id == sec.id
                    )
                )
                count = ent_count_result.scalar_one()
                click.echo(f"  {sec.title}: {count} entries")

        await engine.dispose()

    asyncio.run(_run())


@publish_group.command("freeze")
@click.option("--date", required=True, help="Publication date (YYYY-MM-DD).")
@click.pass_context
def freeze(ctx: click.Context, date: str) -> None:
    """Freeze a publication edition."""
    settings = ctx.obj["settings"]

    async def _run() -> None:
        from datetime import UTC, datetime

        engine = _get_publication_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            from sqlalchemy import select

            from .models import PublicationEdition

            stmt = select(PublicationEdition).where(PublicationEdition.publication_date == date)
            result = await session.execute(stmt)
            edition = result.scalar_one_or_none()

            if edition is None:
                click.echo(f"No edition found for {date}.")
                return

            if edition.status == "frozen":
                click.echo(f"Edition {date} is already frozen.")
                return

            edition.status = "frozen"
            edition.frozen_at = datetime.now(UTC)
            await session.commit()
            click.echo(f"Edition {date} frozen.")

        await engine.dispose()

    asyncio.run(_run())
