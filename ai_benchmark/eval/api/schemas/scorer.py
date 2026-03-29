"""Scorer Pydantic schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class ScorerCreate(BaseModel):
    name: str
    scorer_type: str
    description: str | None = None
    tags: list[str] | None = None


class ScorerResponse(BaseModel):
    id: int
    name: str
    scorer_type: str
    description: str | None
    tags: list | None
    is_archived: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ScorerVersionCreate(BaseModel):
    config: dict
    implementation_ref: str | None = None
    notes: str | None = None


class ScorerVersionResponse(BaseModel):
    id: int
    scorer_id: int
    version_number: int
    config: dict | None
    implementation_ref: str | None
    notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
