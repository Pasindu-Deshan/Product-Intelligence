"""Agent tool-layer tests: validation, context merging, safety."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.tools import TOOLS, FilterParams, execute_tool, tool_schemas
from app.schemas.agent import ConversationContext
from tests.conftest import requires_db


# --- schema / validation (no database needed) -----------------------------


def test_every_tool_exposes_a_json_schema():
    schemas = tool_schemas()
    assert len(schemas) == len(TOOLS)
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["description"]
        assert "properties" in schema["function"]["parameters"]


def test_there_is_no_raw_sql_tool():
    """The single most important property of this layer."""
    names = " ".join(TOOLS).lower()
    for forbidden in ("sql", "query", "execute", "raw"):
        assert forbidden not in names


def test_unknown_tool_is_rejected():
    result = execute_tool("drop_everything", {}, session=None)  # type: ignore[arg-type]
    assert result.ok is False
    assert "No such tool" in result.error


def test_unknown_parameter_is_rejected():
    result = execute_tool(
        "get_time_summary", {"table_name": "worklog_record"}, session=None  # type: ignore[arg-type]
    )
    assert result.ok is False
    assert "Invalid parameters" in result.error


def test_negative_work_item_id_is_rejected():
    result = execute_tool("get_work_item_details", {"work_item_id": -1}, session=None)  # type: ignore[arg-type]
    assert result.ok is False


def test_limit_is_capped():
    result = execute_tool(
        "get_hours_by_work_item", {"limit": 100000}, session=None  # type: ignore[arg-type]
    )
    assert result.ok is False  # 100000 > the declared maximum of 100


# --- context merging -------------------------------------------------------


def test_explicit_arguments_win_over_carried_context():
    ctx = ConversationContext(capability="Authentication", memo_code="DEV")
    filters = FilterParams(memo_code="QA").to_filters(ctx)
    assert filters.capability == "Authentication"  # carried
    assert filters.memo_code == "QA"  # overridden


def test_relative_range_is_resolved_to_explicit_dates():
    filters = FilterParams(relative_range="yesterday").to_filters(None)
    assert filters.date_from == filters.date_to
    assert filters.date_from is not None


def test_unsupported_relative_range_raises():
    from app.agent.tools import ToolParameterError

    with pytest.raises(ToolParameterError):
        FilterParams(relative_range="since forever").to_filters(None)


def test_explicit_iteration_clears_an_inherited_date_window():
    """Otherwise 'and in Sprint 23?' after 'last week' would silently return
    only the overlap of the two."""
    ctx = ConversationContext(date_from=date(2026, 9, 1), date_to=date(2026, 9, 7))
    filters = FilterParams(iteration_path="Product\\Sprint 23").to_filters(ctx)
    assert filters.iteration_path == "Product\\Sprint 23"
    assert filters.date_from is None
    assert filters.date_to is None


def test_context_fields_outside_the_filter_model_are_ignored():
    ctx = ConversationContext(capability="Scheduling", last_intent="CAPABILITY_HOURS")
    filters = FilterParams().to_filters(ctx)
    assert filters.capability == "Scheduling"
    assert not hasattr(filters, "last_intent")


# --- execution against the seeded database --------------------------------


@requires_db
def test_get_time_summary_returns_grounded_numbers(session):
    result = execute_tool("get_time_summary", {"user_id": "bob@example.com"}, session)
    assert result.ok
    assert result.data["total_hours"] == pytest.approx(15.0)
    assert result.filters_applied == {"user_id": "bob@example.com"}


@requires_db
def test_get_hours_by_work_item_returns_evidence_ids(session):
    result = execute_tool("get_hours_by_work_item", {"limit": 3}, session)
    assert result.ok
    assert result.work_item_ids
    assert len(result.work_item_ids) == 3


@requires_db
def test_work_items_by_capability_requires_a_capability(session):
    result = execute_tool("get_work_items_by_capability", {}, session)
    assert result.ok is False
    assert "capability" in result.error.lower()


@requires_db
def test_work_items_by_capability_uses_conversation_context(session):
    ctx = ConversationContext(capability="Authentication")
    result = execute_tool("get_work_items_by_capability", {}, session, ctx)
    assert result.ok
    assert set(result.work_item_ids) == {1234, 1250, 1288}


@requires_db
def test_missing_work_item_returns_a_clear_error_not_an_empty_answer(session):
    result = execute_tool("get_work_item_details", {"work_item_id": 424242}, session)
    assert result.ok is False
    assert "424242" in result.error


@requires_db
def test_unknown_iteration_is_reported_rather_than_returning_zero(session):
    result = execute_tool(
        "get_iteration_summary", {"iteration_path": "Product\\Sprint 99"}, session
    )
    assert result.ok is False
    assert "No time has been logged" in result.error


@requires_db
def test_compare_periods_is_calculated_server_side(session):
    result = execute_tool(
        "compare_periods",
        {
            "period_a": {"iteration_path": "Product\\Sprint 23"},
            "period_b": {"iteration_path": "Product\\Sprint 24"},
        },
        session,
    )
    assert result.ok
    assert result.data["absolute_difference"] == pytest.approx(34.5)
    assert result.data["percentage_difference"] == pytest.approx(287.5)


@requires_db
def test_tool_failure_does_not_leak_internals(session):
    result = execute_tool("get_hours_by_date", {"granularity": "century"}, session)
    assert result.ok is False
    assert "vw_" not in (result.error or "")
    assert "SELECT" not in (result.error or "")
