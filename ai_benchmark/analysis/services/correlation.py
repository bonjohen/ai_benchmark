"""Benchmark correlation matrix: Spearman rank correlation between benchmark variants."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import TYPE_CHECKING

from sqlalchemy import select

from ...models.events import EventRecord
from ..types import CorrelationEntry, CorrelationMatrix

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_correlation_matrix(
    session: AsyncSession,
    *,
    min_overlap: int = 5,
) -> CorrelationMatrix:
    """Compute pairwise Spearman rank correlations between benchmarks."""
    from .benchmark_trends import extract_benchmark_score

    # 1. Query all benchmark events with raw_content
    stmt = (
        select(EventRecord)
        .where(EventRecord.benchmark_variant.is_not(None))
        .where(EventRecord.raw_content.is_not(None))
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # 2. Build score matrix: {model_slug: {benchmark_variant: best_score}}
    score_matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for event in events:
        if not event.model_slug or not event.benchmark_variant:
            continue
        score = extract_benchmark_score(event.raw_content or "", event.benchmark_variant)
        if score is not None:
            current = score_matrix[event.model_slug].get(event.benchmark_variant)
            if current is None or score > current:
                score_matrix[event.model_slug][event.benchmark_variant] = score

    # 3. Get all benchmark variants
    all_benchmarks = sorted({bv for scores in score_matrix.values() for bv in scores})

    if len(all_benchmarks) < 2:
        return CorrelationMatrix(
            min_overlap=min_overlap,
            benchmark_count=len(all_benchmarks),
        )

    # 4. Compute pairwise correlations
    entries = []
    for bench_a, bench_b in combinations(all_benchmarks, 2):
        # Find models with scores on both
        paired = []
        for _model_slug, scores in score_matrix.items():
            if bench_a in scores and bench_b in scores:
                paired.append((scores[bench_a], scores[bench_b]))

        if len(paired) < min_overlap:
            continue

        corr = _spearman_correlation(paired)
        label = _correlation_label(corr)
        entries.append(
            CorrelationEntry(
                benchmark_a=bench_a,
                benchmark_b=bench_b,
                correlation=round(corr, 4),
                overlap_count=len(paired),
                label=label,
            )
        )

    # 5. Detect clusters (groups where all pairwise > 0.7)
    clusters = _detect_clusters(entries, all_benchmarks, threshold=0.7)

    return CorrelationMatrix(
        min_overlap=min_overlap,
        benchmark_count=len(all_benchmarks),
        entries=entries,
        clusters=clusters,
    )


def _spearman_correlation(pairs: list[tuple[float, float]]) -> float:
    """Compute Spearman rank correlation for paired scores."""
    n = len(pairs)
    if n < 2:
        return 0.0

    # Rank each series
    a_vals = [p[0] for p in pairs]
    b_vals = [p[1] for p in pairs]
    a_ranks = _rank(a_vals)
    b_ranks = _rank(b_vals)

    # Spearman: 1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))
    d_sq_sum = sum((a_ranks[i] - b_ranks[i]) ** 2 for i in range(n))
    denom = n * (n**2 - 1)
    if denom == 0:
        return 0.0
    return 1.0 - (6.0 * d_sq_sum) / denom


def _rank(values: list[float]) -> list[float]:
    """Assign average ranks to values (handles ties)."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        # Find all items with the same value
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        # Average rank for tied values
        avg_rank = (i + j + 1) / 2.0  # 1-based average
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _correlation_label(corr: float) -> str:
    """Label a correlation coefficient."""
    abs_corr = abs(corr)
    if abs_corr > 0.8:
        return "redundant"
    if abs_corr > 0.6:
        return "similar"
    if abs_corr > 0.3:
        return "moderate"
    if abs_corr > 0.1:
        return "distinct"
    return "independent"


def _detect_clusters(
    entries: list[CorrelationEntry],
    all_benchmarks: list[str],
    threshold: float,
) -> list[list[str]]:
    """Find groups of benchmarks where all pairwise correlations exceed threshold."""
    # Build adjacency: benchmark pairs with correlation > threshold
    adjacency: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if entry.correlation > threshold:
            adjacency[entry.benchmark_a].add(entry.benchmark_b)
            adjacency[entry.benchmark_b].add(entry.benchmark_a)

    # Simple clique detection: for each benchmark, try to form a cluster
    # with all its neighbors where all pairs are connected
    clusters: list[list[str]] = []
    used: set[str] = set()

    for bench in all_benchmarks:
        if bench in used or bench not in adjacency:
            continue
        # Start with this benchmark and its neighbors
        candidates = {bench} | adjacency[bench]
        # Keep only those where all pairs are connected
        cluster = _maximal_clique(candidates, adjacency)
        if len(cluster) >= 2:
            cluster_sorted = sorted(cluster)
            if cluster_sorted not in clusters:
                clusters.append(cluster_sorted)
                used.update(cluster)

    return clusters


def _maximal_clique(candidates: set[str], adjacency: dict[str, set[str]]) -> set[str]:
    """Find the largest subset where all pairs are connected."""
    candidates_list = sorted(candidates)
    best = set()

    def _backtrack(current: set[str], remaining: list[str]) -> None:
        nonlocal best
        if len(current) > len(best):
            best = set(current)
        for i, node in enumerate(remaining):
            # Check if node is connected to all in current
            if all(node in adjacency.get(c, set()) for c in current):
                current.add(node)
                _backtrack(current, remaining[i + 1 :])
                current.remove(node)

    _backtrack(set(), candidates_list)
    return best
