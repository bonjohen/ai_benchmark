"""Path pattern probing — discovers new paths on vendor domains."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..models.sources import Page, Source

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..collection.fetcher import Fetcher

logger = structlog.get_logger()

# Common path families to probe on vendor domains
PATH_FAMILIES = [
    "/news",
    "/blog",
    "/research",
    "/docs",
    "/changelog",
    "/release-notes",
    "/pricing",
    "/models",
    "/system-cards",
    "/leaderboard",
    "/papers",
]


async def probe_domain(base_domain: str, fetcher: Fetcher) -> list[str]:
    """Probe each path family on the domain via GET request.

    Returns paths that return HTTP 200.
    """
    discovered: list[str] = []
    for path in PATH_FAMILIES:
        url = f"https://{base_domain}{path}"
        try:
            result = await fetcher.fetch(url)
            if result.ok:
                discovered.append(path)
        except Exception:
            continue
    return discovered


async def discover_new_paths(session: AsyncSession, fetcher: Fetcher) -> list[tuple[str, str]]:
    """Discover unconfigured paths on all monitored domains.

    Returns a list of (domain, path) tuples not yet configured as pages.
    """
    # Get all unique base domains
    result = await session.execute(select(Source.base_domain).distinct())
    domains = [row[0] for row in result.all()]

    # Get all configured canonical URLs
    result = await session.execute(select(Page.canonical_url))
    configured_urls = {row[0] for row in result.all()}

    new_paths: list[tuple[str, str]] = []
    for domain in domains:
        discovered = await probe_domain(domain, fetcher)
        for path in discovered:
            url = f"https://{domain}{path}"
            if url not in configured_urls:
                new_paths.append((domain, path))
                logger.info("new_path_discovered", domain=domain, path=path)

    return new_paths
