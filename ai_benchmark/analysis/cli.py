"""CLI commands for the analysis pipeline."""

from __future__ import annotations

import click


@click.group("analyze")
def analyze_group() -> None:
    """Intelligence analysis of collected AI industry data."""
