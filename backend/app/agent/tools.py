"""Controlled tool layer for the agent.

The LLM has no database access. It may only call the functions registered here.
Each tool:

1. validates its parameters through a Pydantic model (unknown fields rejected),
2. delegates to the analytics service, which uses parameterised SQL,
3. returns bounded, structured JSON,
4. is read-only by construction - none of these call a write path.

Adding a tool means adding a Pydantic model plus a handler. There is no
generic "run this SQL" escape hatch, by design.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.analytics.metrics import resolve_relative_range
from app.analytics.service import AnalyticsService
from app.config import get_settings
from app.schemas.agent import ConversationContext, ToolResult
from app.schemas.analytics import AnalyticsFilters, Granularity

logger = logging.getLogger(__name__)
_settings = get_settings()

MAX_EVIDENCE_IDS = 50


# --- shared parameter base -------------------------------------------------


class FilterParams(BaseModel):
    """Filter arguments every analytics tool accepts."""

    model_config = ConfigDict(extra="forbid")

    iteration_path: str | None = Field(
        default=None, description="Exact iteration path, e.g. 'Product\\\\Sprint 24'."
    )
    relative_range: str | None = Field(
        default=None,
        description=(
            "Relative period such as 'last month', 'yesterday', 'last 30 days'. "
            "Resolved server-side into explicit dates."
        ),
    )
    date_from: date | None = None
    date_to: date | None = None
    user_id: str | None = None
    work_item_id: int | None = Field(default=None, ge=1)
    work_item_type: str | None = None
    memo_code: str | None = None
    time_code: str | None = None
    capability: str | None = None
    sub_capability: str | None = None

    def to_filters(self, context: ConversationContext | None = None) -> AnalyticsFilters:
        """Merge conversation context under explicit arguments, then resolve any
        relative range. Explicit arguments always win over carried context."""
        base: dict[str, Any] = {}
        if context:
            base = {
                k: v
                for k, v in context.model_dump(exclude={"last_intent", "last_work_item_ids"}).items()
                if v is not None
            }

        explicit = self.model_dump(exclude={"relative_range"}, exclude_none=True)
        merged = {**base, **explicit}

        if self.relative_range:
            resolved = resolve_relative_range(self.relative_range)
            if resolved is None:
                raise ToolParameterError(
                    f"Unsupported relative period: {self.relative_range!r}."
                )
            merged["date_from"], merged["date_to"] = resolved

        # An explicit iteration overrides any inherited date window, otherwise
        # a carried-over range would silently narrow the iteration.
        if self.iteration_path and not (self.date_from or self.relative_range):
            merged.pop("date_from", None)
            merged.pop("date_to", None)

        allowed = set(AnalyticsFilters.model_fields)
        return AnalyticsFilters(**{k: v for k, v in merged.items() if k in allowed})


class LimitedFilterParams(FilterParams):
    limit: int = Field(default=10, ge=1, le=100)


class CapabilityParams(FilterParams):
    include_sub_capability: bool = False


class WorkItemDetailParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_item_id: int = Field(..., ge=1)


class IterationSummaryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iteration_path: str


class DateParams(FilterParams):
    granularity: Granularity = "day"


class ComparePeriodsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_a: FilterParams
    period_b: FilterParams
    label_a: str = "Period A"
    label_b: str = "Period B"


class DataQualityParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_type: str | None = None
    severity: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ToolParameterError(ValueError):
    """Raised when the model supplies parameters a tool cannot honour."""


# --- registry --------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params_model: type[BaseModel]
    handler: Callable[[AnalyticsService, BaseModel, ConversationContext], ToolResult]

    def json_schema(self) -> dict[str, Any]:
        schema = self.params_model.model_json_schema()
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


def _evidence_ids(rows: list[dict[str, Any]]) -> list[int]:
    ids = [int(r["work_item_id"]) for r in rows if r.get("work_item_id") is not None]
    return ids[:MAX_EVIDENCE_IDS]


# --- handlers --------------------------------------------------------------


def _h_time_summary(svc: AnalyticsService, p: FilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    totals = svc.total_hours(filters)
    return ToolResult(
        data=totals.model_dump(mode="json"),
        filters_applied=filters.describe(),
        row_count=1,
    )


def _h_by_memo(svc: AnalyticsService, p: FilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_memo(filters)
    return ToolResult(data=rows, row_count=len(rows), filters_applied=filters.describe())


def _h_by_time_code(svc: AnalyticsService, p: FilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_time_code(filters)
    return ToolResult(data=rows, row_count=len(rows), filters_applied=filters.describe())


def _h_by_user(svc: AnalyticsService, p: LimitedFilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_user(filters, limit=p.limit)
    return ToolResult(
        data=rows,
        row_count=len(rows),
        truncated=len(rows) >= p.limit,
        filters_applied=filters.describe(),
    )


def _h_by_work_item(svc: AnalyticsService, p: LimitedFilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_work_item(filters, limit=p.limit)
    return ToolResult(
        data=rows,
        row_count=len(rows),
        truncated=len(rows) >= p.limit,
        filters_applied=filters.describe(),
        work_item_ids=_evidence_ids(rows),
    )


def _h_by_work_item_type(svc: AnalyticsService, p: FilterParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_work_item_type(filters)
    return ToolResult(data=rows, row_count=len(rows), filters_applied=filters.describe())


def _h_by_date(svc: AnalyticsService, p: DateParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_date(filters, p.granularity)
    if len(rows) > _settings.max_rows_hard_limit:
        rows = rows[: _settings.max_rows_hard_limit]
        truncated = True
    else:
        truncated = False
    return ToolResult(
        data=[{**r, "period_start": r["period_start"].isoformat()} for r in rows],
        row_count=len(rows),
        truncated=truncated,
        filters_applied=filters.describe(),
    )


def _h_capability_summary(svc: AnalyticsService, p: CapabilityParams, ctx) -> ToolResult:
    filters = p.to_filters(ctx)
    rows = svc.by_capability(filters, include_sub_capability=p.include_sub_capability)
    unclassified = svc.repo.unclassified_work_item_count(filters)
    return ToolResult(
        data={"capabilities": rows, "unclassified_work_item_count": unclassified},
        row_count=len(rows),
        filters_applied=filters.describe(),
    )


def _h_work_items_by_capability(
    svc: AnalyticsService, p: LimitedFilterParams, ctx
) -> ToolResult:
    filters = p.to_filters(ctx)
    if not filters.capability:
        return ToolResult(
            ok=False,
            error="A capability must be supplied (or established earlier in the conversation).",
        )
    rows = svc.by_work_item(filters, limit=p.limit)
    return ToolResult(
        data=rows,
        row_count=len(rows),
        truncated=len(rows) >= p.limit,
        filters_applied=filters.describe(),
        work_item_ids=_evidence_ids(rows),
    )


def _h_work_item_details(
    svc: AnalyticsService, p: WorkItemDetailParams, ctx
) -> ToolResult:
    detail = svc.work_item_detail(p.work_item_id)
    if detail is None:
        return ToolResult(
            ok=False, error=f"No work item {p.work_item_id} exists in the dataset."
        )
    detail = {
        **detail,
        "created_date": _iso(detail.get("created_date")),
        "modified_date": _iso(detail.get("modified_date")),
        "last_sync_date": _iso(detail.get("last_sync_date")),
        "worklogs": [
            {**w, "work_date": _iso(w.get("work_date"))} for w in detail["worklogs"]
        ],
        "capabilities": [
            {**c, "classified_date": _iso(c.get("classified_date"))}
            for c in detail["capabilities"]
        ],
    }
    return ToolResult(data=detail, row_count=1, work_item_ids=[p.work_item_id])


def _h_iteration_summary(
    svc: AnalyticsService, p: IterationSummaryParams, ctx
) -> ToolResult:
    summary = svc.iteration_summary(p.iteration_path)
    if summary.worklog_count == 0:
        return ToolResult(
            ok=False,
            error=(
                f"No time has been logged against iteration '{p.iteration_path}'. "
                "It may not exist or may not be named exactly that."
            ),
        )
    return ToolResult(data=summary.model_dump(mode="json"), row_count=1)


def _h_compare_periods(
    svc: AnalyticsService, p: ComparePeriodsParams, ctx
) -> ToolResult:
    result = svc.compare(
        p.period_a.to_filters(None),
        p.period_b.to_filters(None),
        label_a=p.label_a,
        label_b=p.label_b,
    )
    return ToolResult(data=result.model_dump(mode="json"), row_count=2)


def _h_data_quality(svc: AnalyticsService, p: DataQualityParams, ctx) -> ToolResult:
    summary = svc.data_quality(
        issue_type=p.issue_type, severity=p.severity, limit=p.limit
    )
    return ToolResult(data=summary.model_dump(mode="json"), row_count=summary.total_issues)


def _h_list_iterations(svc: AnalyticsService, p: BaseModel, ctx) -> ToolResult:
    iterations = svc.list_iterations()
    return ToolResult(data={"iterations": iterations}, row_count=len(iterations))


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


# --- registration ----------------------------------------------------------

TOOLS: dict[str, Tool] = {}


def _register(tool: Tool) -> None:
    TOOLS[tool.name] = tool


_register(Tool(
    name="get_time_summary",
    description=(
        "Total logged hours plus worklog, work item and user counts for any "
        "combination of filters. Use for 'how many hours...' questions."
    ),
    params_model=FilterParams,
    handler=_h_time_summary,
))
_register(Tool(
    name="get_hours_by_memo",
    description=(
        "Hours grouped by memo code (the kind of work: development, QA, code "
        "review, support and so on), with each code's share of the filtered total."
    ),
    params_model=FilterParams,
    handler=_h_by_memo,
))
_register(Tool(
    name="get_hours_by_time_code",
    description="Hours grouped by time code (e.g. regular vs overtime).",
    params_model=FilterParams,
    handler=_h_by_time_code,
))
_register(Tool(
    name="get_hours_by_user",
    description="Hours grouped by the person who logged them, highest first.",
    params_model=LimitedFilterParams,
    handler=_h_by_user,
))
_register(Tool(
    name="get_hours_by_work_item",
    description=(
        "Hours grouped by work item, highest first. Use for 'which tickets took "
        "the most time' and for listing the items behind a figure."
    ),
    params_model=LimitedFilterParams,
    handler=_h_by_work_item,
))
_register(Tool(
    name="get_hours_by_work_item_type",
    description="Hours grouped by work item type (Bug, User Story, Task...).",
    params_model=FilterParams,
    handler=_h_by_work_item_type,
))
_register(Tool(
    name="get_hours_by_date",
    description="Hours over time, aggregated by day, week or month.",
    params_model=DateParams,
    handler=_h_by_date,
))
_register(Tool(
    name="get_capability_summary",
    description=(
        "Hours grouped by product capability. Capabilities can overlap - a work "
        "item classified into two capabilities counts in both - so do not sum "
        "them into a grand total. Also reports how many work items are unclassified."
    ),
    params_model=CapabilityParams,
    handler=_h_capability_summary,
))
_register(Tool(
    name="get_work_items_by_capability",
    description="The work items behind a capability, with hours, highest first.",
    params_model=LimitedFilterParams,
    handler=_h_work_items_by_capability,
))
_register(Tool(
    name="get_work_item_details",
    description=(
        "Full detail for one work item: metadata, total hours, capability "
        "classifications and recent worklog entries."
    ),
    params_model=WorkItemDetailParams,
    handler=_h_work_item_details,
))
_register(Tool(
    name="get_iteration_summary",
    description=(
        "Everything about one iteration: totals plus breakdowns by memo code, "
        "time code and work item type."
    ),
    params_model=IterationSummaryParams,
    handler=_h_iteration_summary,
))
_register(Tool(
    name="compare_periods",
    description=(
        "Compare two iterations or two date ranges. Returns both totals, the "
        "absolute difference and the percentage difference, all calculated "
        "server-side. Percentage is null when the first period is zero."
    ),
    params_model=ComparePeriodsParams,
    handler=_h_compare_periods,
))
_register(Tool(
    name="get_data_quality_summary",
    description=(
        "Data-quality problems in the logged time: missing work items, inactive "
        "codes, zero or negative hours, duplicates, sync failures."
    ),
    params_model=DataQualityParams,
    handler=_h_data_quality,
))
_register(Tool(
    name="list_iterations",
    description=(
        "The exact iteration paths available. Call this when the user names a "
        "sprint loosely so you can match it to a real iteration path."
    ),
    params_model=NoParams,
    handler=_h_list_iterations,
))


def tool_schemas() -> list[dict[str, Any]]:
    return [tool.json_schema() for tool in TOOLS.values()]


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    session: Session,
    context: ConversationContext | None = None,
) -> ToolResult:
    """Validate and run one tool call. Never raises to the caller."""
    tool = TOOLS.get(name)
    if tool is None:
        logger.warning("Model requested unknown tool %r", name)
        return ToolResult(ok=False, error=f"No such tool: {name}")

    try:
        params = tool.params_model(**arguments)
    except ValidationError as exc:
        return ToolResult(
            ok=False,
            error=f"Invalid parameters for {name}: {_short_validation_error(exc)}",
        )

    try:
        return tool.handler(AnalyticsService(session), params, context or ConversationContext())
    except ToolParameterError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        # Database/internal errors must not leak to the model or the user.
        logger.exception("Tool %s failed", name)
        return ToolResult(ok=False, error="That query could not be completed.")


def _short_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
