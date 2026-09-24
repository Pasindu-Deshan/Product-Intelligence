"""Read-only repository layer.

Every query in this module:

* reads from ``vw_worklog_base`` (one row per worklog) for anything that sums
  hours, or from ``vw_worklog_analysis`` only where capability grain is wanted;
* passes all user/agent-supplied values as **bound parameters** - no value is
  ever interpolated into the SQL string;
* applies a hard row limit.

Arithmetic lives here and in PostgreSQL. It never lives in the LLM.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas.analytics import AnalyticsFilters, Granularity

logger = logging.getLogger(__name__)
_settings = get_settings()

BASE_VIEW = "vw_worklog_base"
CAPABILITY_VIEW = "vw_worklog_analysis"

# Only these values may ever reach a date_trunc() call.
_GRANULARITY_SQL: dict[str, str] = {
    "day": "day",
    "week": "week",
    "month": "month",
}


def _f(value: Any) -> float:
    """Decimal/None -> float, rounded to 2dp for transport."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(round(value, 2))
    return float(round(Decimal(str(value)), 2))


def _pct(part: float, whole: float) -> float:
    """Deterministic percentage. Never delegated to the LLM."""
    if not whole:
        return 0.0
    return float(round(Decimal(str(part)) / Decimal(str(whole)) * 100, 2))


def build_where(filters: AnalyticsFilters) -> tuple[str, dict[str, Any]]:
    """Translate filters into a parameterised WHERE fragment.

    Returns ``("WHERE ...", params)`` or ``("", {})`` when unfiltered. Column
    names are fixed literals in this module; only values are bound.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if filters.iteration_path:
        clauses.append("iteration_path = :iteration_path")
        params["iteration_path"] = filters.iteration_path
    if filters.date_from:
        clauses.append("work_date >= :date_from")
        params["date_from"] = filters.date_from
    if filters.date_to:
        clauses.append("work_date <= :date_to")
        params["date_to"] = filters.date_to
    if filters.user_id:
        clauses.append("user_id = :user_id")
        params["user_id"] = filters.user_id
    if filters.work_item_id:
        clauses.append("work_item_id = :work_item_id")
        params["work_item_id"] = filters.work_item_id
    if filters.work_item_type:
        clauses.append("work_item_type = :work_item_type")
        params["work_item_type"] = filters.work_item_type
    if filters.memo_code:
        clauses.append("memo_code = :memo_code")
        params["memo_code"] = filters.memo_code
    if filters.time_code:
        clauses.append("time_code = :time_code")
        params["time_code"] = filters.time_code

    # Capability is applied as an EXISTS against work_item_capability rather
    # than by switching to the fanned-out view, so SUM(hours) stays correct.
    if filters.capability:
        sub = (
            "EXISTS (SELECT 1 FROM work_item_capability c "
            "WHERE c.work_item_id = {alias}.work_item_id "
            "AND COALESCE(c.override_capability, c.capability) = :capability"
        )
        params["capability"] = filters.capability
        if filters.sub_capability:
            sub += (
                " AND COALESCE(c.override_sub_capability, c.sub_capability) "
                "= :sub_capability"
            )
            params["sub_capability"] = filters.sub_capability
        clauses.append(sub + ")")

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _where_for(view_alias: str, filters: AnalyticsFilters) -> tuple[str, dict[str, Any]]:
    where, params = build_where(filters)
    return where.format(alias=view_alias) if "{alias}" in where else where, params


class AnalyticsRepository:
    """All deterministic reads for the analytics + agent layers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- helpers ---------------------------------------------------------

    def _rows(self, sql: str, params: dict[str, Any]) -> list[RowMapping]:
        return list(self.session.execute(text(sql), params).mappings())

    def _clamp(self, limit: int | None) -> int:
        if limit is None:
            return _settings.max_rows_default
        return max(1, min(limit, _settings.max_rows_hard_limit))

    # -- totals ----------------------------------------------------------

    def total_hours(self, filters: AnalyticsFilters) -> dict[str, Any]:
        where, params = _where_for("b", filters)
        sql = f"""
            SELECT COALESCE(SUM(hours), 0)          AS total_hours,
                   COUNT(*)                         AS worklog_count,
                   COUNT(DISTINCT work_item_id)     AS work_item_count,
                   COUNT(DISTINCT user_id)          AS user_count
            FROM {BASE_VIEW} b
            {where}
        """
        row = self._rows(sql, params)[0]
        return {
            "total_hours": _f(row["total_hours"]),
            "worklog_count": int(row["worklog_count"]),
            "work_item_count": int(row["work_item_count"]),
            "user_count": int(row["user_count"]),
        }

    # -- breakdowns ------------------------------------------------------

    def hours_by_memo(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, params = _where_for("b", filters)
        sql = f"""
            SELECT memo_code,
                   MAX(memo_description)   AS memo_description,
                   COALESCE(SUM(hours), 0) AS total_hours,
                   COUNT(*)                AS worklog_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY memo_code
            ORDER BY total_hours DESC
        """
        rows = self._rows(sql, params)
        total = sum(_f(r["total_hours"]) for r in rows)
        return [
            {
                "memo_code": r["memo_code"],
                "memo_description": r["memo_description"],
                "total_hours": _f(r["total_hours"]),
                "worklog_count": int(r["worklog_count"]),
                "percentage": _pct(_f(r["total_hours"]), total),
            }
            for r in rows
        ]

    def hours_by_time_code(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, params = _where_for("b", filters)
        sql = f"""
            SELECT time_code,
                   MAX(time_code_name)     AS time_code_name,
                   COALESCE(SUM(hours), 0) AS total_hours,
                   COUNT(*)                AS worklog_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY time_code
            ORDER BY total_hours DESC
        """
        rows = self._rows(sql, params)
        total = sum(_f(r["total_hours"]) for r in rows)
        return [
            {
                "time_code": r["time_code"],
                "time_code_name": r["time_code_name"],
                "total_hours": _f(r["total_hours"]),
                "worklog_count": int(r["worklog_count"]),
                "percentage": _pct(_f(r["total_hours"]), total),
            }
            for r in rows
        ]

    def hours_by_user(
        self, filters: AnalyticsFilters, limit: int | None = None
    ) -> list[dict[str, Any]]:
        where, params = _where_for("b", filters)
        params["limit"] = self._clamp(limit)
        sql = f"""
            SELECT user_id,
                   COALESCE(SUM(hours), 0)      AS total_hours,
                   COUNT(*)                     AS worklog_count,
                   COUNT(DISTINCT work_item_id) AS work_item_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY user_id
            ORDER BY total_hours DESC
            LIMIT :limit
        """
        rows = self._rows(sql, params)
        grand_total = self.total_hours(filters)["total_hours"]
        return [
            {
                "user_id": r["user_id"],
                "total_hours": _f(r["total_hours"]),
                "worklog_count": int(r["worklog_count"]),
                "work_item_count": int(r["work_item_count"]),
                "percentage": _pct(_f(r["total_hours"]), grand_total),
            }
            for r in rows
        ]

    def hours_by_work_item(
        self, filters: AnalyticsFilters, limit: int | None = None
    ) -> list[dict[str, Any]]:
        where, params = _where_for("b", filters)
        params["limit"] = self._clamp(limit)
        sql = f"""
            SELECT work_item_id,
                   MAX(title)              AS title,
                   MAX(work_item_type)     AS work_item_type,
                   MAX(state)              AS state,
                   COALESCE(SUM(hours), 0) AS total_hours,
                   COUNT(*)                AS worklog_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY work_item_id
            ORDER BY total_hours DESC, work_item_id
            LIMIT :limit
        """
        return [
            {
                "work_item_id": int(r["work_item_id"]),
                "title": r["title"],
                "work_item_type": r["work_item_type"],
                "state": r["state"],
                "total_hours": _f(r["total_hours"]),
                "worklog_count": int(r["worklog_count"]),
            }
            for r in self._rows(sql, params)
        ]

    def hours_by_work_item_type(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, params = _where_for("b", filters)
        sql = f"""
            SELECT work_item_type,
                   COALESCE(SUM(hours), 0)      AS total_hours,
                   COUNT(DISTINCT work_item_id) AS work_item_count,
                   COUNT(*)                     AS worklog_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY work_item_type
            ORDER BY total_hours DESC
        """
        rows = self._rows(sql, params)
        total = sum(_f(r["total_hours"]) for r in rows)
        return [
            {
                "work_item_type": r["work_item_type"],
                "total_hours": _f(r["total_hours"]),
                "work_item_count": int(r["work_item_count"]),
                "worklog_count": int(r["worklog_count"]),
                "percentage": _pct(_f(r["total_hours"]), total),
            }
            for r in rows
        ]

    def hours_by_date(
        self, filters: AnalyticsFilters, granularity: Granularity = "day"
    ) -> list[dict[str, Any]]:
        if granularity not in _GRANULARITY_SQL:
            raise ValueError(f"Unsupported granularity: {granularity!r}")
        trunc = _GRANULARITY_SQL[granularity]  # whitelisted literal, not user input
        where, params = _where_for("b", filters)
        sql = f"""
            SELECT date_trunc('{trunc}', work_date)::date AS period_start,
                   COALESCE(SUM(hours), 0)                AS total_hours,
                   COUNT(*)                               AS worklog_count
            FROM {BASE_VIEW} b
            {where}
            GROUP BY 1
            ORDER BY 1
        """
        return [
            {
                "period_start": r["period_start"],
                "total_hours": _f(r["total_hours"]),
                "worklog_count": int(r["worklog_count"]),
            }
            for r in self._rows(sql, params)
        ]

    # -- capability ------------------------------------------------------

    def hours_by_capability(
        self,
        filters: AnalyticsFilters,
        *,
        include_sub_capability: bool = False,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        """Capability aggregation reads the capability-grain view.

        A work item classified into multiple capabilities contributes its hours
        to each - that is intentional here and the reason totals across
        capabilities can exceed the unfiltered grand total. Callers should
        present capability figures as per-capability, not as a partition.
        """
        where, params = _where_for("a", filters)
        conf_clause = ""
        if min_confidence is not None:
            conf_clause = " AND capability_confidence >= :min_confidence"
            params["min_confidence"] = min_confidence

        base_where = where or "WHERE TRUE"
        group_cols = "capability, sub_capability" if include_sub_capability else "capability"
        select_sub = "sub_capability," if include_sub_capability else "NULL AS sub_capability,"

        sql = f"""
            SELECT capability,
                   {select_sub}
                   COALESCE(SUM(hours), 0)      AS total_hours,
                   COUNT(DISTINCT work_item_id) AS work_item_count,
                   COUNT(*)                     AS worklog_count,
                   COUNT(DISTINCT work_item_id) FILTER (
                       WHERE capability_confidence < :low_conf
                         AND capability_human_reviewed IS NOT TRUE
                   ) AS low_confidence_work_items
            FROM {CAPABILITY_VIEW} a
            {base_where} AND capability IS NOT NULL{conf_clause}
            GROUP BY {group_cols}
            ORDER BY total_hours DESC
        """
        params["low_conf"] = _settings.classifier_min_confidence
        rows = self._rows(sql, params)
        total = sum(_f(r["total_hours"]) for r in rows)
        return [
            {
                "capability": r["capability"],
                "sub_capability": r["sub_capability"],
                "total_hours": _f(r["total_hours"]),
                "work_item_count": int(r["work_item_count"]),
                "worklog_count": int(r["worklog_count"]),
                "percentage": _pct(_f(r["total_hours"]), total),
                "low_confidence_work_items": int(r["low_confidence_work_items"]),
            }
            for r in rows
        ]

    def work_items_for_capability(
        self, capability: str, filters: AnalyticsFilters, limit: int | None = None
    ) -> list[dict[str, Any]]:
        scoped = filters.model_copy(update={"capability": capability})
        return self.hours_by_work_item(scoped, limit=limit)

    def unclassified_work_item_count(self, filters: AnalyticsFilters) -> int:
        where, params = _where_for("b", filters)
        base_where = where or "WHERE TRUE"
        sql = f"""
            SELECT COUNT(DISTINCT work_item_id) AS c
            FROM {BASE_VIEW} b
            {base_where} AND has_capability = false
        """
        return int(self._rows(sql, params)[0]["c"])

    # -- work items ------------------------------------------------------

    def get_work_item(self, work_item_id: int) -> dict[str, Any] | None:
        sql = """
            SELECT wi.work_item_id, wi.title, wi.description, wi.work_item_type,
                   wi.state, wi.assigned_to, wi.iteration_path, wi.area_path,
                   wi.created_date, wi.modified_date, wi.last_sync_date
            FROM work_item wi
            WHERE wi.work_item_id = :work_item_id
        """
        rows = self._rows(sql, {"work_item_id": work_item_id})
        return dict(rows[0]) if rows else None

    def get_work_item_capabilities(self, work_item_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT COALESCE(override_capability, capability)          AS capability,
                   COALESCE(override_sub_capability, sub_capability)  AS sub_capability,
                   confidence, model_version, classified_date,
                   is_human_reviewed, reviewed_by
            FROM work_item_capability
            WHERE work_item_id = :work_item_id
            ORDER BY confidence DESC
        """
        out = []
        for r in self._rows(sql, {"work_item_id": work_item_id}):
            d = dict(r)
            d["confidence"] = _f(d["confidence"])
            out.append(d)
        return out

    def get_worklogs_for_work_item(
        self, work_item_id: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        params = {"work_item_id": work_item_id, "limit": self._clamp(limit)}
        sql = f"""
            SELECT worklog_id, user_id, memo_code, memo_description, time_code,
                   time_code_name, hours, work_date, comment, sync_status
            FROM {BASE_VIEW}
            WHERE work_item_id = :work_item_id
            ORDER BY work_date DESC, worklog_id
            LIMIT :limit
        """
        out = []
        for r in self._rows(sql, params):
            d = dict(r)
            d["hours"] = _f(d["hours"])
            out.append(d)
        return out

    def work_items_needing_classification(
        self, limit: int | None = None, *, model_version: str | None = None
    ) -> list[dict[str, Any]]:
        """Work items with no classification, or classified by an older model,
        or whose metadata changed after they were last classified."""
        params: dict[str, Any] = {"limit": self._clamp(limit)}
        version_clause = ""
        if model_version:
            version_clause = " OR wic.model_version <> :model_version"
            params["model_version"] = model_version
        sql = f"""
            SELECT wi.work_item_id, wi.title, wi.description, wi.work_item_type
            FROM work_item wi
            LEFT JOIN work_item_capability wic ON wic.work_item_id = wi.work_item_id
            WHERE wic.work_item_id IS NULL
               OR (wic.is_human_reviewed = false
                   AND (wi.modified_date > wic.classified_date{version_clause}))
            GROUP BY wi.work_item_id, wi.title, wi.description, wi.work_item_type
            ORDER BY wi.work_item_id
            LIMIT :limit
        """
        return [dict(r) for r in self._rows(sql, params)]

    # -- filter options / iterations -------------------------------------

    def list_iterations(self) -> list[str]:
        sql = """
            SELECT DISTINCT iteration_path
            FROM work_item
            WHERE iteration_path IS NOT NULL
            ORDER BY iteration_path
        """
        return [r["iteration_path"] for r in self._rows(sql, {})]

    def iteration_date_range(self, iteration_path: str) -> tuple[date, date] | None:
        sql = f"""
            SELECT MIN(work_date) AS d_from, MAX(work_date) AS d_to
            FROM {BASE_VIEW}
            WHERE iteration_path = :iteration_path
        """
        row = self._rows(sql, {"iteration_path": iteration_path})[0]
        if row["d_from"] is None:
            return None
        return row["d_from"], row["d_to"]

    def filter_options(self) -> dict[str, Any]:
        users = [
            r["user_id"]
            for r in self._rows(
                f"SELECT DISTINCT user_id FROM {BASE_VIEW} "
                "WHERE trim(user_id) <> '' ORDER BY user_id",
                {},
            )
        ]
        types = [
            r["work_item_type"]
            for r in self._rows(
                f"SELECT DISTINCT work_item_type FROM {BASE_VIEW} "
                "WHERE work_item_type IS NOT NULL ORDER BY work_item_type",
                {},
            )
        ]
        memo = [
            dict(r)
            for r in self._rows(
                "SELECT code, description, is_active FROM memo_code_master "
                "ORDER BY is_active DESC, code",
                {},
            )
        ]
        time_codes = [
            dict(r)
            for r in self._rows(
                "SELECT code, name, is_active FROM time_code_master "
                "ORDER BY is_active DESC, code",
                {},
            )
        ]
        caps = [
            r["name"]
            for r in self._rows(
                "SELECT name FROM capability WHERE is_active ORDER BY name", {}
            )
        ]
        return {
            "iterations": self.list_iterations(),
            "users": users,
            "work_item_types": types,
            "memo_codes": memo,
            "time_codes": time_codes,
            "capabilities": caps,
        }

    # -- taxonomy --------------------------------------------------------

    def load_taxonomy(self) -> list[dict[str, Any]]:
        sql = """
            SELECT c.name AS capability, c.description AS capability_description,
                   sc.name AS sub_capability
            FROM capability c
            LEFT JOIN sub_capability sc
                   ON sc.capability_id = c.capability_id AND sc.is_active
            WHERE c.is_active
            ORDER BY c.name, sc.name
        """
        return [dict(r) for r in self._rows(sql, {})]

    # -- data quality ----------------------------------------------------

    def data_quality_issues(
        self,
        issue_type: str | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
        params: dict[str, Any] = {"limit": self._clamp(limit), "offset": max(0, offset)}
        clauses = []
        if issue_type:
            clauses.append("issue_type = :issue_type")
            params["issue_type"] = issue_type
        if severity:
            clauses.append("severity = :severity")
            params["severity"] = severity
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = self._rows(
            f"""SELECT worklog_id, issue_type, severity, detail
                FROM vw_data_quality_issues {where}
                ORDER BY severity, issue_type, worklog_id
                LIMIT :limit OFFSET :offset""",
            params,
        )
        by_type = {
            r["issue_type"]: int(r["c"])
            for r in self._rows(
                "SELECT issue_type, COUNT(*) AS c FROM vw_data_quality_issues "
                "GROUP BY issue_type ORDER BY c DESC",
                {},
            )
        }
        by_sev = {
            r["severity"]: int(r["c"])
            for r in self._rows(
                "SELECT severity, COUNT(*) AS c FROM vw_data_quality_issues "
                "GROUP BY severity",
                {},
            )
        }
        return [dict(r) for r in rows], by_type, by_sev
