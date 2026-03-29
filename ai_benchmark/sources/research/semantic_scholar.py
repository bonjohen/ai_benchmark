"""Semantic Scholar API client and collector for paper enrichment."""

from __future__ import annotations

from ...collection.api_client import APIClient
from ...config.settings import PageConfig, SourceConfig
from ..base import RawItem, SourceCollector


class SemanticScholarCollector(SourceCollector):
    """Collector for Semantic Scholar — API-only source, no HTML extraction.

    Wraps SemanticScholarClient to produce RawItem objects with
    item_type='candidate_paper' for the triage pipeline.
    """

    def __init__(self, source_config: SourceConfig, api_key: str | None = None):
        super().__init__(source_config)
        self.client = SemanticScholarClient(api_key=api_key)

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        """Semantic Scholar is API-only; HTML extraction returns nothing."""
        return []

    async def collect_via_api(self, queries: list[str], limit: int = 5) -> list[RawItem]:
        """Search Semantic Scholar for papers matching queries."""
        items: list[RawItem] = []
        for query in queries:
            results = await self.client.search_paper(query, limit=limit)
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
