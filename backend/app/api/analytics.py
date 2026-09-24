"""Analytics endpoints. Thin: parse, delegate, return. No business logic here."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import FiltersDep, ServiceDep, filter_params
from app.schemas.analytics import (
    AnalyticsFilters,
    CapabilityBreakdownRow,
    ComparisonResult,
    DateBreakdownRow,
    Granularity,
    MemoBreakdownRow,
    TimeCodeBreakdownRow,
    TotalHours,
    UserBreakdownRow,
    WorkItemBreakdownRow,
    WorkItemTypeBreakdownRow,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/time", response_model=TotalHours)
def total_time(service: ServiceDep, filters: FiltersDep) -> TotalHours:
    return service.total_hours(filters)


@router.get("/by-memo", response_model=list[MemoBreakdownRow])
def by_memo(service: ServiceDep, filters: FiltersDep) -> list[dict[str, Any]]:
    return service.by_memo(filters)


@router.get("/by-time-code", response_model=list[TimeCodeBreakdownRow])
def by_time_code(service: ServiceDep, filters: FiltersDep) -> list[dict[str, Any]]:
    return service.by_time_code(filters)


@router.get("/by-user", response_model=list[UserBreakdownRow])
def by_user(
    service: ServiceDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict[str, Any]]:
    return service.by_user(filters, limit=limit)


@router.get("/by-work-item", response_model=list[WorkItemBreakdownRow])
def by_work_item(
    service: ServiceDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict[str, Any]]:
    return service.by_work_item(filters, limit=limit)


@router.get("/by-work-item-type", response_model=list[WorkItemTypeBreakdownRow])
def by_work_item_type(service: ServiceDep, filters: FiltersDep) -> list[dict[str, Any]]:
    return service.by_work_item_type(filters)


@router.get("/by-date", response_model=list[DateBreakdownRow])
def by_date(
    service: ServiceDep,
    filters: FiltersDep,
    granularity: Granularity = "day",
) -> list[dict[str, Any]]:
    return service.by_date(filters, granularity)


@router.get("/by-capability", response_model=list[CapabilityBreakdownRow])
def by_capability(
    service: ServiceDep,
    filters: FiltersDep,
    include_sub_capability: bool = False,
) -> list[dict[str, Any]]:
    """Capability hours can overlap across capabilities - see the view notes.
    The response is per-capability, not a partition of the grand total."""
    return service.by_capability(
        filters, include_sub_capability=include_sub_capability
    )


@router.get("/compare", response_model=ComparisonResult)
def compare(
    service: ServiceDep,
    period_a: Annotated[AnalyticsFilters, Depends(filter_params)],
    iteration_path_b: str | None = None,
    date_from_b: str | None = None,
    date_to_b: str | None = None,
    label_a: str = "Period A",
    label_b: str = "Period B",
) -> ComparisonResult:
    """Compare the standard filter set (period A) against a second period.

    Period B is expressed with the ``*_b`` parameters so the whole comparison
    fits in one GET and stays cacheable/shareable as a URL.
    """
    period_b = AnalyticsFilters(
        iteration_path=iteration_path_b,
        date_from=date_from_b,  # type: ignore[arg-type]
        date_to=date_to_b,  # type: ignore[arg-type]
        user_id=period_a.user_id,
        work_item_type=period_a.work_item_type,
        memo_code=period_a.memo_code,
        time_code=period_a.time_code,
        capability=period_a.capability,
    )
    return service.compare(period_a, period_b, label_a=label_a, label_b=label_b)
