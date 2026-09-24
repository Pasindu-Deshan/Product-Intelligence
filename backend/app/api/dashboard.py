"""Dashboard + reference-data endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import FiltersDep, ServiceDep
from app.schemas.analytics import DashboardSummary, FilterOptions, IterationSummary

router = APIRouter(tags=["dashboard"])


@router.get("/iterations", response_model=list[str])
def list_iterations(service: ServiceDep) -> list[str]:
    return service.list_iterations()


@router.get("/filters", response_model=FilterOptions)
def filter_options(service: ServiceDep) -> FilterOptions:
    """Everything needed to populate the dashboard filter controls."""
    return service.filter_options()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    service: ServiceDep,
    filters: FiltersDep,
    top_n: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DashboardSummary:
    return service.dashboard_summary(filters, top_n=top_n)


@router.get("/iterations/{iteration_path:path}/summary", response_model=IterationSummary)
def iteration_summary(iteration_path: str, service: ServiceDep) -> IterationSummary:
    return service.iteration_summary(iteration_path)
