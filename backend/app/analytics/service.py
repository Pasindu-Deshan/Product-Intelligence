"""Analytics service: orchestrates repository reads into API-shaped results.

This layer owns composition and presentation-neutral derived values. It holds
no SQL and no LLM logic.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import metrics
from app.database.repositories import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsFilters,
    ComparisonResult,
    DashboardSummary,
    DataQualitySummary,
    FilterOptions,
    Granularity,
    IterationSummary,
    PeriodResult,
    TotalHours,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self.repo = AnalyticsRepository(session)

    # -- totals / breakdowns ---------------------------------------------

    def total_hours(self, filters: AnalyticsFilters) -> TotalHours:
        data = self.repo.total_hours(filters)
        return TotalHours(**data, filters_applied=filters.describe())

    def by_memo(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        return self.repo.hours_by_memo(filters)

    def by_time_code(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        return self.repo.hours_by_time_code(filters)

    def by_user(self, filters: AnalyticsFilters, limit: int | None = None):
        return self.repo.hours_by_user(filters, limit=limit)

    def by_work_item(self, filters: AnalyticsFilters, limit: int | None = None):
        return self.repo.hours_by_work_item(filters, limit=limit)

    def by_work_item_type(self, filters: AnalyticsFilters):
        return self.repo.hours_by_work_item_type(filters)

    def by_date(self, filters: AnalyticsFilters, granularity: Granularity = "day"):
        return self.repo.hours_by_date(filters, granularity)

    def by_capability(
        self,
        filters: AnalyticsFilters,
        *,
        include_sub_capability: bool = False,
        min_confidence: float | None = None,
    ):
        return self.repo.hours_by_capability(
            filters,
            include_sub_capability=include_sub_capability,
            min_confidence=min_confidence,
        )

    # -- iteration --------------------------------------------------------

    def iteration_summary(self, iteration_path: str) -> IterationSummary:
        filters = AnalyticsFilters(iteration_path=iteration_path)
        totals = self.repo.total_hours(filters)
        return IterationSummary(
            iteration_path=iteration_path,
            total_hours=totals["total_hours"],
            work_item_count=totals["work_item_count"],
            user_count=totals["user_count"],
            worklog_count=totals["worklog_count"],
            unclassified_work_item_count=self.repo.unclassified_work_item_count(filters),
            hours_by_memo=self.repo.hours_by_memo(filters),
            hours_by_time_code=self.repo.hours_by_time_code(filters),
            hours_by_work_item_type=self.repo.hours_by_work_item_type(filters),
        )

    def list_iterations(self) -> list[str]:
        return self.repo.list_iterations()

    def filter_options(self) -> FilterOptions:
        return FilterOptions(**self.repo.filter_options())

    # -- comparison -------------------------------------------------------

    def compare(
        self,
        filters_a: AnalyticsFilters,
        filters_b: AnalyticsFilters,
        label_a: str = "Period A",
        label_b: str = "Period B",
    ) -> ComparisonResult:
        """Compare two filter sets. Reports the delta only - it makes no
        judgement about whether a change is good or bad."""
        a = self.repo.total_hours(filters_a)
        b = self.repo.total_hours(filters_b)
        return ComparisonResult(
            period_a=PeriodResult(
                label=label_a,
                total_hours=a["total_hours"],
                worklog_count=a["worklog_count"],
                work_item_count=a["work_item_count"],
                filters_applied=filters_a.describe(),
            ),
            period_b=PeriodResult(
                label=label_b,
                total_hours=b["total_hours"],
                worklog_count=b["worklog_count"],
                work_item_count=b["work_item_count"],
                filters_applied=filters_b.describe(),
            ),
            absolute_difference=metrics.absolute_difference(
                a["total_hours"], b["total_hours"]
            ),
            percentage_difference=metrics.percentage_difference(
                a["total_hours"], b["total_hours"]
            ),
        )

    # -- dashboard --------------------------------------------------------

    def dashboard_summary(
        self, filters: AnalyticsFilters, *, top_n: int = 10
    ) -> DashboardSummary:
        totals = self.repo.total_hours(filters)
        span = self._date_span(filters)
        granularity: Granularity = "day" if span is None or span <= 62 else "week"
        return DashboardSummary(
            total_hours=totals["total_hours"],
            work_item_count=totals["work_item_count"],
            user_count=totals["user_count"],
            worklog_count=totals["worklog_count"],
            hours_by_capability=self.repo.hours_by_capability(filters),
            hours_by_memo=self.repo.hours_by_memo(filters),
            hours_by_date=self.repo.hours_by_date(filters, granularity),
            top_work_items=self.repo.hours_by_work_item(filters, limit=top_n),
            filters_applied=filters.describe(),
        )

    @staticmethod
    def _date_span(filters: AnalyticsFilters) -> int | None:
        if filters.date_from and filters.date_to:
            return (filters.date_to - filters.date_from).days
        return None

    # -- work items -------------------------------------------------------

    def work_item_detail(self, work_item_id: int) -> dict[str, Any] | None:
        item = self.repo.get_work_item(work_item_id)
        if item is None:
            return None
        totals = self.repo.total_hours(AnalyticsFilters(work_item_id=work_item_id))
        return {
            **item,
            "total_hours": totals["total_hours"],
            "worklog_count": totals["worklog_count"],
            "capabilities": self.repo.get_work_item_capabilities(work_item_id),
            "worklogs": self.repo.get_worklogs_for_work_item(work_item_id),
        }

    # -- data quality -----------------------------------------------------

    def data_quality(
        self,
        issue_type: str | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> DataQualitySummary:
        issues, by_type, by_sev = self.repo.data_quality_issues(
            issue_type=issue_type, severity=severity, limit=limit, offset=offset
        )
        return DataQualitySummary(
            total_issues=sum(by_type.values()),
            by_type=by_type,
            by_severity=by_sev,
            issues=issues,
        )

    # -- helpers used by the agent ----------------------------------------

    def resolve_iteration_range(self, iteration_path: str) -> tuple[date, date] | None:
        return self.repo.iteration_date_range(iteration_path)
