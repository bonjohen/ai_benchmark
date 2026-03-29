"""Export functions — JSON, CSV, and summary reports."""

from __future__ import annotations

import csv
import io
import json

from ..models.events import ClaimRecord, EventRecord


def events_to_json(events: list[EventRecord]) -> str:
    """Serialize events to JSON string."""
    data = [
        {
            "id": e.id,
            "title": e.title,
            "organization": e.organization,
            "source_type": e.source_type,
            "event_type": e.event_type,
            "model_slug": e.model_slug,
            "published_date": e.published_date,
            "observed_at": e.observed_at.isoformat() if e.observed_at else None,
            "canonical_path": e.canonical_path,
        }
        for e in events
    ]
    return json.dumps(data, indent=2)


def events_to_csv(events: list[EventRecord]) -> str:
    """Serialize events to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "title", "organization", "source_type", "event_type",
        "model_slug", "published_date", "observed_at", "canonical_path",
    ])
    for e in events:
        writer.writerow([
            e.id, e.title, e.organization, e.source_type, e.event_type,
            e.model_slug, e.published_date,
            e.observed_at.isoformat() if e.observed_at else "",
            e.canonical_path,
        ])
    return output.getvalue()


def claims_to_json(claims: list[ClaimRecord]) -> str:
    """Serialize claims to JSON string."""
    data = [
        {
            "id": c.id,
            "event_id": c.event_id,
            "claim_text": c.claim_text,
            "source_type": c.source_type,
            "source_name": c.source_name,
            "confidence_tier": c.confidence_tier,
            "confirmation_status": c.confirmation_status,
            "observed_at": c.observed_at.isoformat() if c.observed_at else None,
        }
        for c in claims
    ]
    return json.dumps(data, indent=2)


def claims_to_csv(claims: list[ClaimRecord]) -> str:
    """Serialize claims to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "event_id", "claim_text", "source_type", "source_name",
        "confidence_tier", "confirmation_status", "observed_at",
    ])
    for c in claims:
        writer.writerow([
            c.id, c.event_id, c.claim_text, c.source_type, c.source_name,
            c.confidence_tier, c.confirmation_status,
            c.observed_at.isoformat() if c.observed_at else "",
        ])
    return output.getvalue()
