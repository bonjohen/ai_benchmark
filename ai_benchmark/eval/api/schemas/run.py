"""Run Pydantic schemas."""

from __future__ import annotations


from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class RunCreate(BaseModel):
    evaluation_version_id: int
    target_config_id: int
    trigger_type: str = "manual"
    priority: int = 0
    machine_profile_id: int | None = None


class RunBatchCreate(BaseModel):
    evaluation_version_id: int
    target_config_ids: list[int]
    execution_type: str = "batch"
    name: str | None = None
    machine_profile_id: int | None = None


class RunResponse(BaseModel):
    id: int
    run_group_id: int | None
    evaluation_version_id: int
    target_config_id: int
    machine_snapshot_id: int | None
    dataset_version_id: int
    status: str
    trigger_type: str
    priority: int
    started_at: datetime | None
    scoring_started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    total_items: int
    completed_items: int
    failed_items: int
    skipped_items: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class RunItemResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    item_index: int
    input_sent: str
    raw_output: str | None
    normalized_output: str | None
    scorer_results: list | None
    overall_pass: bool | None
    error_message: str | None
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_estimate_usd: float | None
    retry_count: int
    trace_id: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RunMetricResponse(BaseModel):
    id: int
    run_id: int
    metric_name: str
    metric_value: float
    metric_metadata: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class RescoreRequest(BaseModel):
    scorer_config: list[dict]
