"""Repository/service tests against the seeded dataset.

Expected values are derived by hand from database/seed/dev_seed.sql so a
regression in the SQL shows up as a wrong number, not just a different number.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.schemas.analytics import AnalyticsFilters
from tests.conftest import requires_db

pytestmark = requires_db

SPRINT_24 = "Product\\Sprint 24"
SPRINT_23 = "Product\\Sprint 23"

# Hand-derived from dev_seed.sql:
#   1234 = 8.0 + 4.5 + 7.0 + 4.0 + 1.0 + 1.0 = 25.5
#   1250 = 8.0          1288 = 6.0 + 0.0 + 3.0 + 1.0 = 10.0
#   1300 = 3.0          -> Sprint 24 = 46.5
#   1301 = 12.0 (Sprint 23)          9999 = 2.0 (orphaned, no iteration)
SPRINT_24_TOTAL = 46.5
GRAND_TOTAL = 60.5


def test_total_hours_unfiltered_includes_orphaned_worklogs(service):
    """WL-9 has no work_item row. It must still count - hiding it would
    understate reality; the data-quality endpoint is what flags it."""
    total = service.total_hours(AnalyticsFilters())
    assert total.total_hours == pytest.approx(GRAND_TOTAL)
    assert total.worklog_count == 14


def test_total_hours_by_iteration(service):
    total = service.total_hours(AnalyticsFilters(iteration_path=SPRINT_24))
    assert total.total_hours == pytest.approx(SPRINT_24_TOTAL)


def test_total_hours_by_user(service):
    total = service.total_hours(AnalyticsFilters(user_id="bob@example.com"))
    assert total.total_hours == pytest.approx(15.0)  # 7.0 QA + 8.0 DEV


def test_total_hours_by_work_item(service):
    total = service.total_hours(AnalyticsFilters(work_item_id=1234))
    assert total.total_hours == pytest.approx(25.5)
    assert total.worklog_count == 6


def test_date_range_filter_is_inclusive(service):
    today = date.today()
    filters = AnalyticsFilters(date_from=today - timedelta(days=1), date_to=today)
    total = service.total_hours(filters)
    assert total.worklog_count == 6  # WL-9 through WL-14


def test_memo_breakdown_percentages_sum_to_100(service):
    rows = service.by_memo(AnalyticsFilters(iteration_path=SPRINT_24))
    assert sum(r["percentage"] for r in rows) == pytest.approx(100.0, abs=0.05)
    qa = next(r for r in rows if r["memo_code"] == "QA")
    assert qa["total_hours"] == pytest.approx(7.0)
    assert qa["memo_description"] == "Quality Assurance"


def test_time_code_breakdown_uses_human_readable_name(service):
    rows = service.by_time_code(AnalyticsFilters())
    reg = next(r for r in rows if r["time_code"] == "REG")
    assert reg["time_code_name"] == "Regular"


def test_by_work_item_is_ordered_by_hours_desc(service):
    rows = service.by_work_item(AnalyticsFilters(), limit=10)
    hours = [r["total_hours"] for r in rows]
    assert hours == sorted(hours, reverse=True)
    assert rows[0]["work_item_id"] == 1234
    assert rows[0]["title"] == "Implement SSO"


def test_by_work_item_respects_limit(service):
    assert len(service.by_work_item(AnalyticsFilters(), limit=2)) == 2


def test_by_work_item_type_counts_distinct_items(service):
    rows = service.by_work_item_type(AnalyticsFilters())
    bug = next(r for r in rows if r["work_item_type"] == "Bug")
    assert bug["work_item_count"] == 2  # 1300 and the orphaned 9999
    assert bug["total_hours"] == pytest.approx(5.0)


def test_by_date_daily_and_monthly(service):
    daily = service.by_date(AnalyticsFilters(), "day")
    monthly = service.by_date(AnalyticsFilters(), "month")
    assert sum(r["total_hours"] for r in daily) == pytest.approx(GRAND_TOTAL)
    assert sum(r["total_hours"] for r in monthly) == pytest.approx(GRAND_TOTAL)
    assert len(monthly) <= len(daily)


def test_by_date_rejects_unknown_granularity(service):
    with pytest.raises(ValueError):
        service.by_date(AnalyticsFilters(), "fortnight")  # type: ignore[arg-type]


def test_capability_filter_does_not_double_count(service):
    """The capability filter is an EXISTS, not a join, so filtering by
    capability must not multiply hours."""
    auth = service.total_hours(AnalyticsFilters(capability="Authentication"))
    # Work items 1234 (25.5) + 1250 (8.0) + 1288 (10.0) = 43.5
    assert auth.total_hours == pytest.approx(43.5)


def test_capability_breakdown(service):
    rows = service.by_capability(AnalyticsFilters())
    auth = next(r for r in rows if r["capability"] == "Authentication")
    assert auth["total_hours"] == pytest.approx(43.5)
    assert auth["work_item_count"] == 3


def test_capability_and_memo_filters_combine(service):
    qa_in_auth = service.total_hours(
        AnalyticsFilters(capability="Authentication", memo_code="QA")
    )
    assert qa_in_auth.total_hours == pytest.approx(7.0)


def test_iteration_summary(service):
    summary = service.iteration_summary(SPRINT_24)
    assert summary.total_hours == pytest.approx(SPRINT_24_TOTAL)
    assert summary.work_item_count == 4
    assert summary.user_count == 4  # alice, bob, carol + the blank user on WL-14
    assert {r["memo_code"] for r in summary.hours_by_memo} >= {"DEV", "QA", "REVIEW"}


def test_compare_periods(service):
    result = service.compare(
        AnalyticsFilters(iteration_path=SPRINT_23),
        AnalyticsFilters(iteration_path=SPRINT_24),
        label_a="Sprint 23",
        label_b="Sprint 24",
    )
    assert result.period_a.total_hours == pytest.approx(12.0)
    assert result.period_b.total_hours == pytest.approx(SPRINT_24_TOTAL)
    assert result.absolute_difference == pytest.approx(34.5)
    assert result.percentage_difference == pytest.approx(287.5)


def test_compare_against_empty_period_yields_null_percentage(service):
    result = service.compare(
        AnalyticsFilters(iteration_path="Product\\Nonexistent"),
        AnalyticsFilters(iteration_path=SPRINT_24),
    )
    assert result.period_a.total_hours == 0.0
    assert result.percentage_difference is None


def test_filters_applied_is_echoed_back(service):
    total = service.total_hours(AnalyticsFilters(memo_code="QA"))
    assert total.filters_applied == {"memo_code": "QA"}


def test_invalid_date_range_is_rejected_at_the_contract(service):
    with pytest.raises(ValueError):
        AnalyticsFilters(date_from=date(2026, 9, 30), date_to=date(2026, 9, 1))


def test_unclassified_work_item_count(service):
    # Every seeded work item is classified; only the orphan 9999 is not.
    assert service.repo.unclassified_work_item_count(AnalyticsFilters()) == 1


def test_data_quality_finds_the_seeded_problems(service):
    summary = service.data_quality(limit=100)
    assert summary.by_type["MISSING_WORK_ITEM"] == 1
    assert summary.by_type["INACTIVE_MEMO_CODE"] == 1
    assert summary.by_type["INACTIVE_TIME_CODE"] == 1
    assert summary.by_type["ZERO_HOURS"] == 1
    assert summary.by_type["MISSING_COMMENT"] == 1
    assert summary.by_type["MISSING_USER"] == 1
    assert summary.by_type["SYNC_FAILURE"] == 1


def test_data_quality_can_filter_by_severity(service):
    summary = service.data_quality(severity="high", limit=100)
    assert all(i.severity == "high" for i in summary.issues)


def test_work_item_detail(service):
    detail = service.work_item_detail(1234)
    assert detail is not None
    assert detail["total_hours"] == pytest.approx(25.5)
    assert detail["capabilities"][0]["capability"] == "Authentication"
    assert len(detail["worklogs"]) == 6


def test_work_item_detail_missing_returns_none(service):
    assert service.work_item_detail(424242) is None
