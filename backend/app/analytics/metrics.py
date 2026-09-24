"""Pure, dependency-free metric helpers.

Kept separate from the repository so the arithmetic can be unit-tested without
a database, and so it is obvious where numbers come from. The LLM never
performs any of these calculations.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def round2(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def percentage(part: float, whole: float) -> float:
    """Share of ``whole`` represented by ``part``. Zero whole -> 0.0."""
    if not whole:
        return 0.0
    return round2(Decimal(str(part)) / Decimal(str(whole)) * 100)


def absolute_difference(a: float, b: float) -> float:
    """b - a, i.e. the change moving from period A to period B."""
    return round2(Decimal(str(b)) - Decimal(str(a)))


def percentage_difference(a: float, b: float) -> float | None:
    """Percentage change from A to B.

    Returns ``None`` when A is zero: percentage change from zero is undefined
    and reporting "infinite" or "100%" would be misleading. Callers surface the
    None explicitly rather than substituting a number.
    """
    if not a:
        return None
    return round2((Decimal(str(b)) - Decimal(str(a))) / Decimal(str(a)) * 100)


def add_percentages(rows: list[dict], value_key: str = "total_hours") -> list[dict]:
    total = sum(float(r.get(value_key, 0) or 0) for r in rows)
    for row in rows:
        row["percentage"] = percentage(float(row.get(value_key, 0) or 0), total)
    return rows


# --- Relative date resolution ---------------------------------------------
# Used by the agent to turn phrases like "last month" into a concrete, stated
# date range. The resolved range is always echoed back to the user so the
# assumption is visible rather than silent.


def resolve_relative_range(phrase: str, today: date | None = None) -> tuple[date, date] | None:
    """Map a small, closed set of relative phrases to explicit date ranges."""
    today = today or date.today()
    p = phrase.strip().lower()

    if p == "today":
        return today, today
    if p == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if p in {"this week", "current week"}:
        start = today - timedelta(days=today.weekday())
        return start, today
    if p in {"last week", "previous week"}:
        this_start = today - timedelta(days=today.weekday())
        return this_start - timedelta(days=7), this_start - timedelta(days=1)
    if p in {"this month", "current month"}:
        return today.replace(day=1), today
    if p in {"last month", "previous month"}:
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if p in {"last 7 days", "past 7 days"}:
        return today - timedelta(days=6), today
    if p in {"last 30 days", "past 30 days"}:
        return today - timedelta(days=29), today
    if p in {"last 90 days", "past 90 days"}:
        return today - timedelta(days=89), today
    return None


SUPPORTED_RELATIVE_PHRASES: tuple[str, ...] = (
    "today",
    "yesterday",
    "this week",
    "last week",
    "this month",
    "last month",
    "last 7 days",
    "last 30 days",
    "last 90 days",
)
