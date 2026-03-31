"""HTML rendering for publication editions — self-contained for email/static distribution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EditionResult


def edition_to_html(edition: EditionResult) -> str:
    """Render a complete edition as a self-contained HTML document."""
    sections_html = []
    for section in edition.sections:
        if not section.entries:
            continue

        entries_html = []
        for entry in section.entries:
            badge_cls = {
                "confirmed": "#34a853",
                "unconfirmed": "#f9ab00",
                "conflicted": "#ea4335",
            }.get(entry.verification_status, "#666")

            meta_parts = []
            if entry.organization:
                meta_parts.append(entry.organization)
            if entry.model_slug:
                meta_parts.append(entry.model_slug)
            if entry.benchmark_name:
                meta_parts.append(entry.benchmark_name)
            meta_parts.append(f"{entry.source_count} source(s)")

            why = ""
            if entry.why_it_matters:
                why = (
                    f'<p style="margin:4px 0 0;font-size:13px;color:#555;">'
                    f"<strong>Why it matters:</strong> {_esc(entry.why_it_matters)}</p>"
                )

            entries_html.append(
                f'<div style="background:#fff;border:1px solid #e0e0e0;'
                f'border-radius:6px;padding:10px 14px;margin-bottom:6px;">'
                f'<div style="display:flex;align-items:center;gap:6px;">'
                f'<strong style="color:#1a73e8;">{entry.rank}.</strong> '
                f"<strong>{_esc(entry.title)}</strong> "
                f'<span style="font-size:11px;padding:2px 6px;border-radius:3px;'
                f'background:#f5f5f5;color:{badge_cls};">{entry.verification_status}</span>'
                f"</div>"
                f'<p style="margin:4px 0 0;font-size:13px;color:#666;">'
                f"{_esc(entry.summary)}</p>"
                f"{why}"
                f'<p style="margin:4px 0 0;font-size:11px;color:#999;">'
                f"{' &middot; '.join(_esc(p) for p in meta_parts)}"
                f" &middot; Score: {entry.score:.2f}</p>"
                f"</div>"
            )

        sections_html.append(
            f'<div style="margin-bottom:24px;">'
            f'<h2 style="font-size:18px;border-bottom:2px solid #1a73e8;'
            f'padding-bottom:4px;margin-bottom:8px;">{_esc(section.title)}</h2>'
            + (
                f'<p style="font-size:13px;color:#666;margin-bottom:8px;">'
                f"{_esc(section.summary)}</p>"
                if section.summary
                else ""
            )
            + "\n".join(entries_html)
            + "</div>"
        )

    body = "\n".join(sections_html)
    summary_html = (
        f'<p style="font-style:italic;color:#666;">{_esc(edition.summary)}</p>'
        if edition.summary
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily AI Benchmark — {_esc(edition.publication_date)}</title>
<style>
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       max-width:800px;margin:0 auto;padding:20px;color:#333;background:#fafafa;
       line-height:1.6; }}
</style>
</head>
<body>
<h1 style="font-size:22px;">Daily AI Benchmark — {_esc(edition.publication_date)}</h1>
{summary_html}
{body}
<hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
<p style="font-size:12px;color:#999;">AI Benchmark Intelligence Pipeline</p>
</body>
</html>"""


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
