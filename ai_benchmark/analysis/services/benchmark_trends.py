"""Benchmark trends: leaderboards, score extraction, and time series."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ...models.events import EventRecord
from ..types import BenchmarkDataPoint, BenchmarkSummary, Leaderboard

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


def extract_benchmark_score(raw_content: str, benchmark_name: str | None = None) -> float | None:
    """Best-effort score extraction from unstructured text.

    Priority order:
    1. Percentage: '92.3%'
    2. Elo-like: 'Elo: 1287', 'rating: 1350', 'score: 85.1'
    3. Decimal between 0 and 1 exclusive: '0.623'
    4. Bare integer 2-4 digits (not in model slug context)
    """
    if not raw_content:
        return None

    # 1. Percentage pattern
    pct_match = re.search(r"(\d+\.?\d*)\s*%", raw_content)
    if pct_match:
        return float(pct_match.group(1))

    # 2. Elo-like pattern
    elo_match = re.search(r"(?:elo|rating|score)[:\s]+(\d+\.?\d*)", raw_content, re.IGNORECASE)
    if elo_match:
        return float(elo_match.group(1))

    # 3. Decimal between 0 and 1
    dec_match = re.search(r"(\d+\.\d+)", raw_content)
    if dec_match:
        val = float(dec_match.group(1))
        if 0 < val < 1:
            return val

    # 4. Bare integer 2-4 digits
    int_match = re.search(r"\b(\d{2,4})\b", raw_content)
    if int_match:
        return float(int_match.group(1))

    return None


async def list_benchmarks(session: AsyncSession) -> list[BenchmarkSummary]:
    """All tracked benchmarks with entry counts."""
    stmt = (
        select(
            EventRecord.benchmark_variant,
            func.count(EventRecord.id).label("entry_count"),
            func.max(EventRecord.published_date).label("latest_date"),
        )
        .where(EventRecord.benchmark_variant.is_not(None))
        .group_by(EventRecord.benchmark_variant)
        .order_by(func.count(EventRecord.id).desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    summaries = []
    for row in rows:
        # Find top scorer for this benchmark
        top_stmt = (
            select(EventRecord)
            .where(EventRecord.benchmark_variant == row.benchmark_variant)
            .where(EventRecord.raw_content.is_not(None))
            .order_by(EventRecord.published_date.desc())
            .limit(5)
        )
        top_result = await session.execute(top_stmt)
        top_events = list(top_result.scalars().all())

        top_model = None
        top_score = None
        for event in top_events:
            score = extract_benchmark_score(event.raw_content or "", row.benchmark_variant)
            if score is not None and (top_score is None or score > top_score):
                top_score = score
                top_model = event.model_slug

        summaries.append(
            BenchmarkSummary(
                benchmark_name=row.benchmark_variant,
                entry_count=row.entry_count,
                latest_date=row.latest_date,
                top_model=top_model,
                top_score=top_score,
            )
        )
    return summaries


async def get_benchmark_leaderboard(
    session: AsyncSession,
    benchmark_name: str,
    *,
    as_of: datetime | None = None,
) -> Leaderboard:
    """Point-in-time leaderboard. Default: latest data."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.benchmark_variant.ilike(f"%{benchmark_name}%"))
        .order_by(EventRecord.published_date.desc())
    )
    if as_of:
        stmt = stmt.where(EventRecord.observed_at <= as_of)

    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Group by model_slug, take latest entry per model
    latest_by_model: dict[str, EventRecord] = {}
    for event in events:
        slug = event.model_slug or "unknown"
        if slug not in latest_by_model:
            latest_by_model[slug] = event

    # Extract scores and build data points
    entries: list[BenchmarkDataPoint] = []
    for slug, event in latest_by_model.items():
        score = extract_benchmark_score(event.raw_content or "", event.benchmark_variant)
        entries.append(
            BenchmarkDataPoint(
                model_slug=slug,
                score=score,
                date=event.published_date or event.observed_at.strftime("%Y-%m-%d"),
                source_name=event.organization,
                benchmark_variant=event.benchmark_variant or benchmark_name,
            )
        )

    # Sort by score descending (None last)
    entries.sort(key=lambda e: (e.score is None, -(e.score or 0)))

    as_of_str = as_of.strftime("%Y-%m-%d") if as_of else "latest"
    return Leaderboard(
        benchmark_name=benchmark_name,
        as_of=as_of_str,
        entries=entries,
    )


async def get_benchmark_timeline(
    session: AsyncSession,
    benchmark_name: str,
    *,
    model_slug: str | None = None,
) -> list[BenchmarkDataPoint]:
    """Time series of scores, optionally filtered by model."""
    stmt = (
        select(EventRecord)
        .where(EventRecord.benchmark_variant.ilike(f"%{benchmark_name}%"))
        .order_by(EventRecord.published_date.asc())
    )
    if model_slug:
        stmt = stmt.where(EventRecord.model_slug == model_slug)

    result = await session.execute(stmt)
    events = list(result.scalars().all())

    points = []
    for event in events:
        score = extract_benchmark_score(event.raw_content or "", event.benchmark_variant)
        points.append(
            BenchmarkDataPoint(
                model_slug=event.model_slug or "unknown",
                score=score,
                date=event.published_date or event.observed_at.strftime("%Y-%m-%d"),
                source_name=event.organization,
                benchmark_variant=event.benchmark_variant or benchmark_name,
            )
        )
    return points
