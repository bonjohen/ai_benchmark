"""Static file export for publication editions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ..types import EditionResult

logger = structlog.get_logger(__name__)


async def export_static(
    edition: EditionResult,
    export_path: str,
    formats: list[str] | None = None,
) -> list[str]:
    """Write edition to static files at the configured export path.

    Returns list of written file paths.
    """
    if formats is None:
        formats = ["markdown", "json"]

    out_dir = Path(export_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    date = edition.publication_date

    if "markdown" in formats:
        from ..formatters.markdown import edition_to_markdown

        md_path = out_dir / f"edition-{date}.md"
        md_path.write_text(edition_to_markdown(edition), encoding="utf-8")
        written.append(str(md_path))
        logger.info("static_export_written", path=str(md_path), format="markdown")

    if "json" in formats:
        from ..formatters.json_export import edition_to_json

        json_path = out_dir / f"edition-{date}.json"
        json_path.write_text(edition_to_json(edition), encoding="utf-8")
        written.append(str(json_path))
        logger.info("static_export_written", path=str(json_path), format="json")

    return written
