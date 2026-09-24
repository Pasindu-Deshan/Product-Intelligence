"""Pure arithmetic tests. These are the numbers the LLM is forbidden to compute."""

from __future__ import annotations

from datetime import date

import pytest

from app.analytics import metrics


@pytest.mark.parametrize(
    "part,whole,expected",
    [(7.0, 42.5, 16.47), (0.0, 10.0, 0.0), (10.0, 10.0, 100.0), (5.0, 0.0, 0.0)],
)
def test_percentage(part, whole, expected):
    assert metrics.percentage(part, whole) == expected


def test_absolute_difference_is_b_minus_a():
    assert metrics.absolute_difference(40.0, 50.0) == 10.0
    assert metrics.absolute_difference(50.0, 40.0) == -10.0


def test_percentage_difference():
    assert metrics.percentage_difference(40.0, 50.0) == 25.0
    assert metrics.percentage_difference(50.0, 40.0) == -20.0


def test_percentage_difference_from_zero_is_undefined_not_infinite():
    # Reporting "100%" or "inf" here would be a fabricated number.
    assert metrics.percentage_difference(0.0, 10.0) is None


def test_rounding_is_half_up_not_bankers():
    assert metrics.round2(2.675) == 2.68


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("yesterday", (date(2026, 9, 23), date(2026, 9, 23))),
        ("last month", (date(2026, 8, 1), date(2026, 8, 31))),
        ("this month", (date(2026, 9, 1), date(2026, 9, 24))),
        ("last week", (date(2026, 9, 14), date(2026, 9, 20))),
        ("last 7 days", (date(2026, 9, 18), date(2026, 9, 24))),
    ],
)
def test_resolve_relative_range(phrase, expected):
    assert metrics.resolve_relative_range(phrase, date(2026, 9, 24)) == expected


def test_unknown_relative_phrase_returns_none():
    assert metrics.resolve_relative_range("since the dawn of time") is None


def test_add_percentages_sums_to_100():
    rows = [{"total_hours": 30.0}, {"total_hours": 10.0}, {"total_hours": 10.0}]
    out = metrics.add_percentages(rows)
    assert [r["percentage"] for r in out] == [60.0, 20.0, 20.0]
