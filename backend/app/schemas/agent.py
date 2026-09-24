"""Pydantic contracts for the conversational agent."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "TOTAL_HOURS",
    "MEMO_HOURS",
    "TIME_CODE_HOURS",
    "USER_HOURS",
    "WORK_ITEM_HOURS",
    "WORK_ITEM_TYPE_HOURS",
    "DATE_HOURS",
    "CAPABILITY_HOURS",
    "CAPABILITY_WORK_ITEMS",
    "WORK_ITEM_DETAIL",
    "ITERATION_SUMMARY",
    "COMPARISON",
    "DATA_QUALITY",
    "CLARIFICATION_NEEDED",
    "UNSUPPORTED",
]


class ConversationContext(BaseModel):
    """Structured carry-over between turns.

    Deliberately narrow: only resolved filter values live here, never free text
    and never raw rows. A follow-up such as "how much of that was QA?" is
    answered by merging the new memo filter over this object, not by replaying
    the transcript into a query.
    """

    model_config = ConfigDict(extra="forbid")

    iteration_path: str | None = None
    capability: str | None = None
    sub_capability: str | None = None
    memo_code: str | None = None
    time_code: str | None = None
    user_id: str | None = None
    work_item_id: int | None = None
    work_item_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    last_intent: Intent | None = None
    last_work_item_ids: list[int] = Field(default_factory=list)

    def merge(self, updates: dict[str, Any]) -> "ConversationContext":
        """Return a new context with non-null updates applied."""
        clean = {k: v for k, v in updates.items() if v is not None and k in self.model_fields}
        return self.model_copy(update=clean)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)
    reset_context: bool = False


class EvidenceItem(BaseModel):
    work_item_id: int
    title: str | None = None
    hours: float | None = None


class Evidence(BaseModel):
    work_item_ids: list[int] = Field(default_factory=list)
    work_items: list[EvidenceItem] = Field(default_factory=list)
    worklog_count: int | None = None
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    tools_used: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    analytics: dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence = Field(default_factory=Evidence)
    context: ConversationContext = Field(default_factory=ConversationContext)
    conversation_id: str
    needs_clarification: bool = False
    unsupported: bool = False


class ToolResult(BaseModel):
    """What a tool hands back to the agent loop."""

    model_config = ConfigDict(extra="allow")

    ok: bool = True
    error: str | None = None
    data: Any = None
    row_count: int | None = None
    truncated: bool = False
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    work_item_ids: list[int] = Field(default_factory=list)
