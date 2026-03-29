"""Dataset Pydantic schemas."""

from __future__ import annotations


from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    source: str | None = None
    tags: list[str] | None = None


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: str | None
    source: str | None
    tags: list | None
    is_archived: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    input_text: str
    expected_output: str | None = None
    context: str | None = None
    metadata: dict | None = None


class DatasetVersionCreate(BaseModel):
    items: list[TestCaseCreate]
    notes: str | None = None


class DatasetVersionResponse(BaseModel):
    id: int
    dataset_id: int
    version_number: int
    item_count: int
    checksum: str | None
    notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class TestCaseResponse(BaseModel):
    id: int
    dataset_version_id: int
    item_index: int
    input_text: str
    expected_output: str | None
    context: str | None
    metadata: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ItemFilterRequest(BaseModel):
    tags: list[str] | None = None
    task_families: list[str] | None = None
    min_tokens: int | None = None
    max_tokens: int | None = None
    difficulty: str | None = None
