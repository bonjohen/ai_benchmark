"""Meta/Llama source collector: GitHub org (releases, repos) and landing page."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from bs4 import BeautifulSoup

from ..collection.api_client import APIClient
from .base import RawItem, SourceCollector, extract_title

if TYPE_CHECKING:
    from datetime import date

    from ..collection.differ import DiffResult
    from ..collection.fetcher import Fetcher
    from ..collection.snapshot import SnapshotManager
    from ..config.settings import PageConfig


class GitHubOrgClient(APIClient):
    """GitHub API client for polling organization repos and releases."""

    base_url = "https://api.github.com"

    def auth_header(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"token {self.api_key}"}
        return {}

    async def get_org_repos(self, org: str, per_page: int = 30) -> list[dict]:
        """Get recent repos for a GitHub org."""
        return await self.get_paginated(
            f"/orgs/{org}/repos",
            params={"sort": "updated", "direction": "desc"},
            per_page=per_page,
            max_pages=1,
        )

    async def get_repo_releases(self, owner: str, repo: str, per_page: int = 10) -> list[dict]:
        """Get recent releases for a repo."""
        return await self.get_paginated(
            f"/repos/{owner}/{repo}/releases",
            per_page=per_page,
            max_pages=1,
        )


class MetaCollector(SourceCollector):
    """Collector for Meta's open-source AI and Llama GitHub org."""

    _API_PAGE_TYPES: ClassVar[set[str]] = {"github"}

    def __init__(self, source_config, github_token: str | None = None):
        super().__init__(source_config)
        self.gh_client = GitHubOrgClient(api_key=github_token)

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Override to use GitHub API for github org pages."""
        if "github" in page.page_type:
            # Extract org from URL like https://github.com/meta-llama
            match = re.search(r"github\.com/([^/]+)", page.canonical_url)
            org = match.group(1) if match else "meta-llama"
            items = await self.collect_github(org)
            return items, None
        return await super().collect_page(
            page,
            fetcher,
            snapshot_mgr,
            page_id,
            since_date=since_date,
        )

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        if "rss" in page.page_type:
            return self._extract_google_news_rss(html)
        if "github" in page.page_type:
            # GitHub pages are handled via API in collect_page override
            return []
        if "landing" in page.page_type:
            return self._extract_landing(html)
        if "model" in page.page_type:
            return self._extract_model_docs(html)
        return []

    def _extract_landing(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("section, article, .card"):
            title_el = section.select_one("h2, h3, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if title:
                items.append(
                    RawItem(
                        title=title,
                        body=section.get_text(strip=True),
                        item_type="landing_section",
                    )
                )
        return items

    def _extract_model_docs(self, html: str) -> list[RawItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[RawItem] = []
        for section in soup.select("tr, .model-card, section, h3"):
            text = section.get_text(strip=True)
            if text and len(text) > 5:
                items.append(
                    RawItem(
                        title=extract_title(text),
                        body=text,
                        item_type="model_entry",
                    )
                )
        return items

    async def collect_github(self, org: str = "meta-llama") -> list[RawItem]:
        """Collect items from the GitHub API for the Meta Llama org."""
        items: list[RawItem] = []
        try:
            repos = await self.gh_client.get_org_repos(org)
            for repo in repos[:20]:
                items.append(
                    RawItem(
                        title=repo.get("full_name", ""),
                        url=repo.get("html_url", ""),
                        date_text=repo.get("updated_at", ""),
                        body=repo.get("description", "") or "",
                        item_type="github_repo",
                        metadata={
                            "stars": repo.get("stargazers_count", 0),
                            "language": repo.get("language", ""),
                        },
                    )
                )

            # Get releases for key repos
            for repo_name in ["llama-models", "llama", "PurpleLlama"]:
                try:
                    releases = await self.gh_client.get_repo_releases(org, repo_name)
                    for rel in releases[:5]:
                        items.append(
                            RawItem(
                                title=f"{repo_name}: {rel.get('name', rel.get('tag_name', ''))}",
                                url=rel.get("html_url", ""),
                                date_text=rel.get("published_at", ""),
                                body=rel.get("body", "")[:500],
                                item_type="github_release",
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return items
