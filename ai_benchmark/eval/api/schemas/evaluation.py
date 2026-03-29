"""Evaluation Pydantic schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class EvaluationCreate(BaseModel):
    name: str
    description: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    suite_name: str | None = None
    execution_mode: str = "sequential"


class EvaluationUpdate(BaseModel):
    description: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    suite_name: str | None = None
    execution_mode: str | None = None
    is_archived: bool | None = None


class EvaluationResponse(BaseModel):
    id: int
    name: str
    description: str | None
    owner: str | None
    tags: list | None
    suite_name: str | None
    execution_mode: str
    is_archived: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class EvaluationVersionCreate(BaseModel):
    dataset_version_id: int
    scorer_config: list[dict]
    prompt_template: str | None = None
    preprocessing: dict | None = None
    pass_criteria: dict | None = None
    notes: str | None = None


class EvaluationVersionResponse(BaseModel):
    id: int
    evaluation_id: int
    version_number: int
    dataset_version_id: int
    scorer_config: list | None
    prompt_template: str | None
    preprocessing: dict | None
    pass_criteria: dict | None
    notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
