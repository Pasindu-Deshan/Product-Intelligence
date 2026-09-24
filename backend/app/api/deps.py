"""Shared FastAPI dependencies."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsService
from app.database.connection import get_read_session
from app.schemas.analytics import AnalyticsFilters

SessionDep = Annotated[Session, Depends(get_read_session)]


def get_analytics_service(session: SessionDep) -> AnalyticsService:
    return AnalyticsService(session)


ServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


def filter_params(
    iteration_path: Annotated[str | None, Query(max_length=1000)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: Annotated[str | None, Query(max_length=100)] = None,
    work_item_id: Annotated[int | None, Query(ge=1)] = None,
    work_item_type: Annotated[str | None, Query(max_length=100)] = None,
    memo_code: Annotated[str | None, Query(max_length=100)] = None,
    time_code: Annotated[str | None, Query(max_length=100)] = None,
    capability: Annotated[str | None, Query(max_length=255)] = None,
    sub_capability: Annotated[str | None, Query(max_length=255)] = None,
) -> AnalyticsFilters:
    """Parse and validate the shared query-string filters.

    Pydantic raises on an inverted date range, which FastAPI turns into a 422 -
    the caller gets a clear message instead of a silently empty result set.
    """
    return AnalyticsFilters(
        iteration_path=iteration_path,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        work_item_id=work_item_id,
        work_item_type=work_item_type,
        memo_code=memo_code,
        time_code=time_code,
        capability=capability,
        sub_capability=sub_capability,
    )


FiltersDep = Annotated[AnalyticsFilters, Depends(filter_params)]
