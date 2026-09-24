"""Pydantic contracts for filters and analytics responses."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Granularity = Literal["day", "week", "month"]


class AnalyticsFilters(BaseModel):
    """The single filter object every analytics call accepts.

    Values are always passed to SQL as bound parameters; none of these strings
    is ever interpolated into a query.
    """

    model_config = ConfigDict(extra="forbid")

    iteration_path: str | None = Field(
        default=None,
        max_length=1000,
        description="Exact ADO iteration path, e.g. 'Product\\\\Sprint 24'.",
    )
    date_from: date | None = None
    date_to: date | None = None
    user_id: str | None = Field(default=None, max_length=100)
    work_item_id: int | None = Field(default=None, ge=1)
    work_item_type: str | None = Field(default=None, max_length=100)
    memo_code: str | None = Field(default=None, max_length=100)
    time_code: str | None = Field(default=None, max_length=100)
    capability: str | None = Field(default=None, max_length=255)
    sub_capability: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check_date_order(self) -> "AnalyticsFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self

    def describe(self) -> dict[str, object]:
        """Human/agent-readable summary of what was actually applied."""
        return {k: v for k, v in self.model_dump(mode="json").items() if v is not None}


class Page(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# --- Result rows -----------------------------------------------------------


class TotalHours(BaseModel):
    total_hours: float
    worklog_count: int
    work_item_count: int
    user_count: int
    filters_applied: dict[str, object] = Field(default_factory=dict)


class MemoBreakdownRow(BaseModel):
    memo_code: str
    memo_description: str | None = None
    total_hours: float
    worklog_count: int
    percentage: float


class TimeCodeBreakdownRow(BaseModel):
    time_code: str
    time_code_name: str | None = None
    total_hours: float
    worklog_count: int
    percentage: float


class UserBreakdownRow(BaseModel):
    user_id: str
    total_hours: float
    worklog_count: int
    work_item_count: int
    percentage: float


class WorkItemBreakdownRow(BaseModel):
    work_item_id: int
    title: str | None = None
    work_item_type: str | None = None
    state: str | None = None
    total_hours: float
    worklog_count: int


class WorkItemTypeBreakdownRow(BaseModel):
    work_item_type: str
    total_hours: float
    work_item_count: int
    worklog_count: int
    percentage: float


class DateBreakdownRow(BaseModel):
    period_start: date
    total_hours: float
    worklog_count: int


class CapabilityBreakdownRow(BaseModel):
    capability: str
    sub_capability: str | None = None
    total_hours: float
    work_item_count: int
    worklog_count: int
    percentage: float
    low_confidence_work_items: int = 0


class IterationSummary(BaseModel):
    iteration_path: str
    total_hours: float
    work_item_count: int
    user_count: int
    worklog_count: int
    unclassified_work_item_count: int
    hours_by_memo: list[MemoBreakdownRow]
    hours_by_time_code: list[TimeCodeBreakdownRow]
    hours_by_work_item_type: list[WorkItemTypeBreakdownRow]


class PeriodResult(BaseModel):
    label: str
    total_hours: float
    worklog_count: int
    work_item_count: int
    filters_applied: dict[str, object] = Field(default_factory=dict)


class ComparisonResult(BaseModel):
    period_a: PeriodResult
    period_b: PeriodResult
    absolute_difference: float
    percentage_difference: float | None = Field(
        default=None,
        description="None when period A is zero hours (percentage is undefined).",
    )


class DashboardSummary(BaseModel):
    total_hours: float
    work_item_count: int
    user_count: int
    worklog_count: int
    hours_by_capability: list[CapabilityBreakdownRow]
    hours_by_memo: list[MemoBreakdownRow]
    hours_by_date: list[DateBreakdownRow]
    top_work_items: list[WorkItemBreakdownRow]
    filters_applied: dict[str, object] = Field(default_factory=dict)


class FilterOptions(BaseModel):
    iterations: list[str]
    users: list[str]
    work_item_types: list[str]
    memo_codes: list[dict[str, object]]
    time_codes: list[dict[str, object]]
    capabilities: list[str]


class DataQualityIssueRow(BaseModel):
    worklog_id: str
    issue_type: str
    severity: str
    detail: str


class DataQualitySummary(BaseModel):
    total_issues: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    issues: list[DataQualityIssueRow]
