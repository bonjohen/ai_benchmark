"""Research triage pipeline: candidate → enrichment → promotion."""

from __future__ import annotations

from datetime import datetime, timezone, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.research import CandidatePaper, EnrichedPaper
from ..sources.research.semantic_scholar import SemanticScholarClient

# Keywords that indicate relevance to tracked models/benchmarks
RELEVANCE_KEYWORDS = {
    "benchmark", "leaderboard", "evaluation", "llm", "language model",
    "gpt", "claude", "gemini", "llama", "mistral", "grok",
    "openai", "anthropic", "google", "meta", "deepmind",
    "swe-bench", "livebench", "humaneval", "arena", "gaia",
    "agent", "reasoning", "coding", "safety", "alignment",
}


async def ingest_candidate(
    session: AsyncSession,
    title: str,
    arxiv_id: str | None,
    authors: str | None,
    categories: str | None,
    abstract_url: str | None,
    discovered_via: str,
) -> CandidatePaper | None:
    """Stage 1: Add a paper to the candidate queue. Skip if already exists."""
    if arxiv_id:
        existing = await session.execute(
            select(CandidatePaper).where(CandidatePaper.arxiv_id == arxiv_id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return None

    paper = CandidatePaper(
        title=title,
        arxiv_id=arxiv_id,
        authors=authors,
        categories=categories,
        abstract_url=abstract_url,
        discovered_via=discovered_via,
        status="pending",
    )
    session.add(paper)
    await session.flush()
    return paper


async def enrich_candidate(
    session: AsyncSession,
    candidate: CandidatePaper,
    s2_client: SemanticScholarClient,
) -> CandidatePaper:
    """Stage 2: Enrich a candidate paper with Semantic Scholar metadata.

    Sets status to 'enriched' if relevant, 'rejected' if not.
    """
    try:
        if candidate.arxiv_id:
            paper_data = await s2_client.get_paper_by_arxiv(candidate.arxiv_id)
        else:
            results = await s2_client.search_paper(candidate.title, limit=1)
            if not results:
                candidate.status = "rejected"
                return candidate
            paper_data = results[0]

        # Check relevance
        combined = f"{paper_data.get('title', '')} {paper_data.get('abstract', '')}".lower()
        relevance_score = sum(1 for kw in RELEVANCE_KEYWORDS if kw in combined)

        if relevance_score < 2:
            candidate.status = "rejected"
            return candidate

        candidate.status = "enriched"
        return candidate

    except Exception:
        # API failures don't reject — leave as pending for retry
        candidate.retry_count = (candidate.retry_count or 0) + 1
        candidate.last_retry_at = datetime.now(UTC)
        return candidate


async def promote_to_enriched(
    session: AsyncSession,
    candidate: CandidatePaper,
    paper_data: dict,
) -> EnrichedPaper:
    """Stage 3: Promote an enriched candidate to the authoritative store."""
    authors_list = paper_data.get("authors", [])
    author_names = ", ".join(a.get("name", "") for a in authors_list) if authors_list else None

    enriched = EnrichedPaper(
        candidate_id=candidate.id,
        title=paper_data.get("title", candidate.title),
        arxiv_id=candidate.arxiv_id,
        semantic_scholar_id=paper_data.get("paperId"),
        authors=author_names,
        abstract=paper_data.get("abstract"),
        venue=paper_data.get("venue"),
        citation_count=paper_data.get("citationCount", 0),
        code_url=paper_data.get("externalIds", {}).get("GitHub"),
        enriched_at=datetime.now(UTC),
    )
    session.add(enriched)
    candidate.status = "promoted"
    await session.flush()
    return enriched


async def get_pending_candidates(session: AsyncSession, limit: int = 50) -> list[CandidatePaper]:
    """Get candidates awaiting enrichment, skipping those that exceeded retry limit."""
    result = await session.execute(
        select(CandidatePaper)
        .where(CandidatePaper.status == "pending")
        .where(CandidatePaper.retry_count < 3)
        .order_by(CandidatePaper.discovered_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def enrich_pending_candidates(
    session: AsyncSession,
    s2_client: SemanticScholarClient,
    limit: int = 50,
) -> int:
    """Scheduled job: enrich all pending candidates and promote relevant ones.

    Returns the number of papers promoted.
    """
    candidates = await get_pending_candidates(session, limit=limit)
    promoted_count = 0

    for candidate in candidates:
        enriched = await enrich_candidate(session, candidate, s2_client)

        if enriched.status == "enriched":
            # Re-fetch paper data for promotion
            try:
                if candidate.arxiv_id:
                    paper_data = await s2_client.get_paper_by_arxiv(candidate.arxiv_id)
                else:
                    results = await s2_client.search_paper(candidate.title, limit=1)
                    paper_data = results[0] if results else {}
                if paper_data:
                    await promote_to_enriched(session, candidate, paper_data)
                    promoted_count += 1
            except Exception:
                pass  # Promotion failure is not fatal; paper stays enriched

    await session.flush()
    return promoted_count
