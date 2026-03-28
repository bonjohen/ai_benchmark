"""Comparison and report Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CompareRequest(BaseModel):
    run_ids: list[int]


class CompareResponse(BaseModel):
    metric_deltas: dict
    scorer_breakdown: dict
    item_diffs: list[dict]


class ConfigDiffRequest(BaseModel):
    target_ids: list[int]


class ConfigDiffResponse(BaseModel):
    diffs: dict


class ReportRequest(BaseModel):
    run_ids: list[int]
    group_by: str | None = None
    format: str = "json"


class PresetCreate(BaseModel):
    name: str
    config: dict


class PresetResponse(BaseModel):
    name: str
    config: dict
