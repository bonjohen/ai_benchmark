"""Audit trail service — logs data transmission events."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from ..models.audit import AuditLogEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def log_data_sent(
    session: AsyncSession,
    *,
    run_id: int,
    item_index: int | None = None,
    provider: str,
    endpoint_url: str | None = None,
    model_name: str | None = None,
    data_classification: str = "standard",
    input_size_bytes: int | None = None,
    details: dict | None = None,
) -> AuditLogEntry:
    """Log that data was sent to a provider/endpoint."""
    entry = AuditLogEntry(
        run_id=run_id,
        item_index=item_index,
        action="data_sent",
        provider=provider,
        endpoint_url=endpoint_url,
        model_name=model_name,
        data_classification=data_classification,
        input_size_bytes=input_size_bytes,
        details=json.dumps(details) if details else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def log_data_received(
    session: AsyncSession,
    *,
    run_id: int,
    item_index: int | None = None,
    provider: str,
    endpoint_url: str | None = None,
    model_name: str | None = None,
    data_classification: str = "standard",
    output_size_bytes: int | None = None,
    details: dict | None = None,
) -> AuditLogEntry:
    """Log that data was received from a provider/endpoint."""
    entry = AuditLogEntry(
        run_id=run_id,
        item_index=item_index,
        action="data_received",
        provider=provider,
        endpoint_url=endpoint_url,
        model_name=model_name,
        data_classification=data_classification,
        output_size_bytes=output_size_bytes,
        details=json.dumps(details) if details else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def log_run_event(
    session: AsyncSession,
    *,
    run_id: int,
    action: str,
    provider: str,
    endpoint_url: str | None = None,
    model_name: str | None = None,
    data_classification: str = "standard",
    details: dict | None = None,
) -> AuditLogEntry:
    """Log a run lifecycle event (start, complete, fail)."""
    entry = AuditLogEntry(
        run_id=run_id,
        action=action,
        provider=provider,
        endpoint_url=endpoint_url,
        model_name=model_name,
        data_classification=data_classification,
        details=json.dumps(details) if details else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_audit_log(
    session: AsyncSession,
    *,
    run_id: int | None = None,
    action: str | None = None,
    provider: str | None = None,
    limit: int = 100,
) -> list[AuditLogEntry]:
    """Query audit log entries with optional filters."""
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.created_at.desc())
    if run_id is not None:
        stmt = stmt.where(AuditLogEntry.run_id == run_id)
    if action:
        stmt = stmt.where(AuditLogEntry.action == action)
    if provider:
        stmt = stmt.where(AuditLogEntry.provider == provider)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
