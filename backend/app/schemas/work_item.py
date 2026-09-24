"""Work-item response contracts."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class CapabilityAssignment(BaseModel):
    capability: str
    sub_capability: str | None = None
    confidence: float
    model_version: str
    classified_date: datetime | None = None
    is_human_reviewed: bool = False
    reviewed_by: str | None = None


class WorklogEntry(BaseModel):
    worklog_id: str
    user_id: str
    memo_code: str
    memo_description: str | None = None
    time_code: str
    time_code_name: str | None = None
    hours: float
    work_date: date
    comment: str
    sync_status: str


class WorkItemDetail(BaseModel):
    work_item_id: int
    title: str | None = None
    description: str | None = None
    work_item_type: str | None = None
    state: str | None = None
    assigned_to: str | None = None
    iteration_path: str | None = None
    area_path: str | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    last_sync_date: datetime | None = None
    total_hours: float
    worklog_count: int
    capabilities: list[CapabilityAssignment] = []
    worklogs: list[WorklogEntry] = []
