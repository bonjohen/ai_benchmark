"""GitHub discovery collector — polls watched orgs for new repos, releases, and tags."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...collection.api_client import APIClient
from ..base import RawItem, SourceCollector

if TYPE_CHECKING:
    from datetime import date

    from ...collection.differ import DiffResult
    from ...collection.fetcher import Fetcher
    from ...collection.snapshot import SnapshotManager
    from ...config.settings import PageConfig

# Default organizations to watch for AI model activity
WATCHED_ORGS = [
    "openai",
    "anthropics",
    "google-deepmind",
    "meta-llama",
    "mistralai",
    "xai-org",
    "cohere-ai",
]


class GitHubDiscoveryClient(APIClient):
    """GitHub API client for discovery across multiple organizations."""

    base_url = "https://api.github.com"

    def auth_header(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"token {self.api_key}"}
        return {}

    async def get_org_repos(self, org: str, per_page: int = 10) -> list[dict]:
        return await self.get_paginated(
            f"/orgs/{org}/repos",
            params={"sort": "updated", "direction": "desc"},
            per_page=per_page,
            max_pages=1,
        )

    async def get_repo_releases(self, owner: str, repo: str, per_page: int = 5) -> list[dict]:
        return await self.get_paginated(
            f"/repos/{owner}/{repo}/releases",
            per_page=per_page,
            max_pages=1,
        )

    async def get_repo_tags(self, owner: str, repo: str, per_page: int = 5) -> list[dict]:
        return await self.get_paginated(
            f"/repos/{owner}/{repo}/tags",
            per_page=per_page,
            max_pages=1,
        )


class GitHubDiscoveryCollector(SourceCollector):
    """Collector for GitHub activity across watched AI organizations.

    Tracks new repos, releases, README changes, and tags. Discovery-only
    source used to surface signals, not as authoritative confirmation.
    """

    CONFIDENCE_TIER = "low_discovery"

    def __init__(self, source_config, github_token: str | None = None):
        super().__init__(source_config)
        self.client = GitHubDiscoveryClient(api_key=github_token)

    async def collect_page(
        self,
        page: PageConfig,
        fetcher: Fetcher,
        snapshot_mgr: SnapshotManager,
        page_id: int,
        since_date: date | None = None,
    ) -> tuple[list[RawItem], DiffResult | None]:
        """Override to use GitHub API instead of HTML scraping."""
        if "github" in page.page_type:
            # Extract org or repo from URL
            match = re.search(r"github\.com/([^/]+)(?:/([^/]+))?", page.canonical_url)
            if match:
                org = match.group(1)
                repo = match.group(2)
                if repo:
                    # Single repo — get releases
                    items = await self._collect_repo(org, repo)
                else:
                    # Org page — get recent repos and releases
                    items = await self._collect_org(org)
                return items, None
        if "dataset" in page.page_type:
            # HuggingFace dataset pages — fall through to HTML
            pass
        return await super().collect_page(
            page,
            fetcher,
            snapshot_mgr,
            page_id,
            since_date=since_date,
        )

    async def _collect_org(self, org: str) -> list[RawItem]:
        """Collect repos and releases for a single GitHub org."""
        items: list[RawItem] = []
        try:
            repos = await self.client.get_org_repos(org)
        except Exception:
            return items
        for repo in repos:
            items.append(
                RawItem(
                    title=repo.get("full_name", ""),
                    url=repo.get("html_url", ""),
                    date_text=repo.get("pushed_at") or repo.get("updated_at", ""),
                    body=repo.get("description", "") or "",
                    item_type="github_repo",
                    metadata={
                        "source": "github_discovery",
                        "org": org,
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language"),
                        "confidence_tier": self.CONFIDENCE_TIER,
                    },
                )
            )
            # Check releases for notable repos
            repo_name = repo.get("name", "")
            if repo.get("stargazers_count", 0) > 50:
                try:
                    releases = await self.client.get_repo_releases(org, repo_name)
                    for rel in releases[:3]:
                        items.append(
                            RawItem(
                                title=(
                                    f"{org}/{repo_name}: "
                                    f"{rel.get('name') or rel.get('tag_name', '')}"
                                ),
                                url=rel.get("html_url", ""),
                                date_text=rel.get("published_at", ""),
                                body=(rel.get("body") or "")[:500],
                                item_type="github_release",
                                metadata={
                                    "source": "github_discovery",
                                    "org": org,
                                    "repo": repo_name,
                                    "tag": rel.get("tag_name", ""),
                                    "confidence_tier": self.CONFIDENCE_TIER,
                                },
                            )
                        )
                except Exception:
                    continue
        return items

    async def _collect_repo(self, owner: str, repo: str) -> list[RawItem]:
        """Collect releases for a specific repository."""
        items: list[RawItem] = []
        try:
            releases = await self.client.get_repo_releases(owner, repo)
            for rel in releases[:5]:
                items.append(
                    RawItem(
                        title=(f"{owner}/{repo}: {rel.get('name') or rel.get('tag_name', '')}"),
                        url=rel.get("html_url", ""),
                        date_text=rel.get("published_at", ""),
                        body=(rel.get("body") or "")[:500],
                        item_type="github_release",
                        metadata={
                            "source": "github_discovery",
                            "org": owner,
                            "repo": repo,
                            "tag": rel.get("tag_name", ""),
                            "confidence_tier": self.CONFIDENCE_TIER,
                        },
                    )
                )
        except Exception:
            pass
        return items

    def extract_items(self, html: str, page: PageConfig) -> list[RawItem]:
        # Fallback for non-GitHub pages (e.g., HuggingFace dataset pages)
        return []

    async def collect_orgs(self, orgs: list[str] | None = None) -> list[RawItem]:
        """Poll watched organizations for new repos and releases."""
        orgs = orgs or WATCHED_ORGS
        items: list[RawItem] = []

        for org in orgs:
            try:
                repos = await self.client.get_org_repos(org)
            except Exception:
                continue

            for repo in repos:
                items.append(
                    RawItem(
                        title=repo.get("full_name", ""),
                        url=repo.get("html_url", ""),
                        date_text=repo.get("pushed_at") or repo.get("updated_at", ""),
                        body=repo.get("description", "") or "",
                        item_type="github_repo",
                        metadata={
                            "source": "github_discovery",
                            "org": org,
                            "stars": repo.get("stargazers_count", 0),
                            "language": repo.get("language"),
                            "confidence_tier": self.CONFIDENCE_TIER,
                        },
                    )
                )

                # Check releases for key repos
                repo_name = repo.get("name", "")
                if repo.get("stargazers_count", 0) > 50:
                    try:
                        releases = await self.client.get_repo_releases(org, repo_name)
                        for rel in releases[:3]:
                            items.append(
                                RawItem(
                                    title=(
                                        f"{org}/{repo_name}: "
                                        f"{rel.get('name') or rel.get('tag_name', '')}"
                                    ),
                                    url=rel.get("html_url", ""),
                                    date_text=rel.get("published_at", ""),
                                    body=(rel.get("body") or "")[:500],
                                    item_type="github_release",
                                    metadata={
                                        "source": "github_discovery",
                                        "org": org,
                                        "repo": repo_name,
                                        "tag": rel.get("tag_name", ""),
                                        "confidence_tier": self.CONFIDENCE_TIER,
                                    },
                                )
                            )
                    except Exception:
                        continue

        return items
