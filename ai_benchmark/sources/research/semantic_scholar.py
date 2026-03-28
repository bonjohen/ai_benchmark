"""Semantic Scholar API client for paper enrichment."""

from __future__ import annotations

from ...collection.api_client import APIClient


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
                "fields": "title,authors,year,citationCount,venue,externalIds,abstract,url,references,citations",
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
