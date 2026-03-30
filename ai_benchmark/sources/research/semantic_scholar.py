"""Semantic Scholar API client and collector for paper enrichment."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from ...collection.api_client import APIClient
from ..base import RawItem, SourceCollector

if TYPE_CHECKING:
    from datetime import date

    from ...collection.differ import DiffResult
    from ...collection.fetcher import Fetcher
    from ...collection.snapshot import SnapshotManager
    from ...config.settings import PageConfig, SourceConfig

logger = structlog.get_logger()

# Default queries for discovery polling
_DEFAULT_QUERIES = [
    "large language model benchmark evaluation",
    "LLM reasoning safety alignment",
    "frontier AI model release",
]


class SemanticScholarCollector(SourceCollector):
    """Collector for Semantic Scholar — API-only source, no HTML extraction.

    Wraps SemanticScholarClient to produce RawItem objects with
    item_type='candidate_paper' for the triage pipeline.
    """

    def __init__(self, source_config: SourceConfig, api_key: str | None = None):
        super().__init__(source_config)
        self.client = SemanticScholarClient(api_key=api_key)

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Override to use Semantic Scholar API instead of HTML."""
        if "api" in page.page_type:
            if not self.client.api_key:
                logger.warning(
                    "semantic_scholar_no_api_key",
                    hint="Set AI_BENCH_SEMANTIC_SCHOLAR_API_KEY for higher rate limits",
                )
            items = await self.collect_via_api(_DEFAULT_QUERIES)
            return items, None
        return await super().collect_page(
            page,
            fetcher,
            snapshot_mgr,
            page_id,
            since_date=since_date,
        )

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        """Semantic Scholar is API-only; HTML extraction returns nothing."""
        return []

    async def collect_via_api(self, queries: list[str], limit: int = 5) -> list[RawItem]:
        """Search Semantic Scholar for papers matching queries."""
        items: list[RawItem] = []
        for i, query in enumerate(queries):
            if i > 0:
                await asyncio.sleep(3.0)
            try:
                results = await self.client.search_paper(query, limit=limit)
            except Exception:
                logger.warning(
                    "semantic_scholar_query_failed",
                    query=query,
                    exc_info=True,
                )
                continue
            for paper in results:
                authors = ", ".join(a.get("name", "") for a in paper.get("authors", []))
                ext_ids = paper.get("externalIds", {}) or {}
                arxiv_id = ext_ids.get("ArXiv", "")
                items.append(
                    RawItem(
                        title=paper.get("title", ""),
                        url=paper.get("url", ""),
                        body=paper.get("abstract", "") or "",
                        item_type="candidate_paper",
                        metadata={
                            "arxiv_id": arxiv_id,
                            "authors": authors,
                            "categories": "",
                            "source": "semantic_scholar",
                            "semantic_scholar_id": paper.get("paperId", ""),
                            "citation_count": paper.get("citationCount", 0),
                        },
                    )
                )
        return items


class SemanticScholarClient(APIClient):
    """Client for the Semantic Scholar Academic Graph API.

    Used for enrichment of candidate papers, not direct polling.
    """

    base_url = "https://api.semanticscholar.org/graph/v1"

    def auth_header(self) -> dict[str, str]:
        if self.api_key:
            return {"x-api-key": self.api_key}
        return {}

    async def search_paper(self, query: str, limit: int = 5) -> list[dict]:
        """Search for papers by title or keywords."""
        data = await self.get(
            "/paper/search",
            params={
                "query": query,
                "limit": limit,
                "fields": "title,authors,year,citationCount,venue,externalIds,abstract,url",
            },
        )
        return data.get("data", [])

    async def get_paper(self, paper_id: str) -> dict:
        """Get detailed paper info by Semantic Scholar ID or arXiv ID."""
        return await self.get(
            f"/paper/{paper_id}",
            params={
                "fields": (
                    "title,authors,year,citationCount,venue,"
                    "externalIds,abstract,url,references,citations"
                ),
            },
        )

    async def get_paper_by_arxiv(self, arxiv_id: str) -> dict:
        """Get paper info by arXiv ID."""
        return await self.get_paper(f"ArXiv:{arxiv_id}")

    async def get_recommendations(self, paper_id: str, limit: int = 5) -> list[dict]:
        """Get recommended papers similar to the given one."""
        data = await self.get(
            f"/recommendations/v1/papers/forpaper/{paper_id}",
            params={"limit": limit, "fields": "title,authors,year,citationCount,venue"},
        )
        return data.get("recommendedPapers", [])
