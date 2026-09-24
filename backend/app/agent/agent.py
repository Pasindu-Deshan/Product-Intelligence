"""Product Intelligence agent orchestration.

The loop is deliberately boring:

    guardrail -> (tool call -> execute -> feed result back)* -> explain

Numbers only ever enter the answer through a tool result. The model's job is
to choose tools, pass parameters and narrate what came back.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agent.conversation import Conversation, ConversationStore, conversation_store
from app.agent.intent import IntentResult, detect_intent
from app.agent.llm import LLMClient
from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.agent.tools import TOOLS, execute_tool, tool_schemas
from app.config import get_settings
from app.database.repositories import AnalyticsRepository
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    Evidence,
    EvidenceItem,
    ToolResult,
)

logger = logging.getLogger(__name__)

CONTEXT_KEYS = {
    "iteration_path",
    "capability",
    "sub_capability",
    "memo_code",
    "time_code",
    "user_id",
    "work_item_id",
    "work_item_type",
    "date_from",
    "date_to",
}


class ProductIntelligenceAgent:
    def __init__(
        self,
        session: Session,
        llm: LLMClient | None = None,
        store: ConversationStore | None = None,
        settings=None,
    ) -> None:
        self.session = session
        self.llm = llm or LLMClient()
        self.store = store or conversation_store
        self.settings = settings or get_settings()

    # -- entry point ------------------------------------------------------

    def ask(self, request: ChatRequest) -> ChatResponse:
        conversation = self.store.get_or_create(request.conversation_id)

        if request.reset_context:
            conversation.reset_context()

        intent = detect_intent(request.message, self.llm)

        if intent.intent == "UNSUPPORTED":
            return self._refusal(
                conversation,
                request.message,
                intent,
            )

        if intent.intent == "CLARIFICATION_NEEDED":
            return self._clarification(
                conversation,
                request.message,
                intent,
            )

        return self._run_tool_loop(
            conversation,
            request,
            intent,
        )


    # -- main loop --------------------------------------------------------

    def _run_tool_loop(
        self,
        conversation: Conversation,
        request: ChatRequest,
        intent: IntentResult,
    ) -> ChatResponse:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": AGENT_SYSTEM_PROMPT,
            },
            {
                "role": "system",
                "content": self._context_note(conversation),
            },
            *conversation.messages(),
            {
                "role": "user",
                "content": request.message,
            },
        ]

        analytics: dict[str, Any] = {}
        tools_used: list[str] = []
        work_item_ids: list[int] = []
        filters_applied: dict[str, Any] = {}
        worklog_count: int | None = None
        answer = ""

        for iteration in range(
            self.settings.llm_max_tool_iterations
        ):
            response = self.llm.chat(
                messages,
                tools=tool_schemas(),
            )

            if not response.tool_calls:
                answer = (
                    response.content or ""
                ).strip()
                break

            messages.append(
                response.raw_message
            )

            for call in response.tool_calls:
                result = execute_tool(
                    call.name,
                    call.arguments,
                    self.session,
                    conversation.context,
                )

                tools_used.append(call.name)

                if result.ok:
                    analytics[call.name] = result.data

                    filters_applied.update(
                        result.filters_applied
                    )

                    work_item_ids.extend(
                        result.work_item_ids
                    )

                    worklog_count = (
                        _extract_worklog_count(result)
                        or worklog_count
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": result.model_dump_json(
                            exclude_none=True
                        ),
                    }
                )

        else:
            logger.warning(
                "Agent hit the tool iteration limit (%s)",
                self.settings.llm_max_tool_iterations,
            )

            answer = (
                "I wasn't able to narrow that down within a reasonable "
                "number of steps. Could you make the question more "
                "specific - for example by naming an iteration or a "
                "date range?"
            )

        if not answer:
            answer = (
                "I retrieved the figures but could not summarise them. "
                "The raw results are included below."
            )

        conversation.apply_context(
            {
                k: v
                for k, v in filters_applied.items()
                if k in CONTEXT_KEYS
            }
        )

        conversation.apply_context(
            {
                "last_intent": intent.intent
            }
        )

        if work_item_ids:
            conversation.context.last_work_item_ids = _dedupe(
                work_item_ids
            )

        conversation.add_turn(
            "user",
            request.message,
        )

        conversation.add_turn(
            "assistant",
            answer,
        )

        self.store.save(conversation)

        return ChatResponse(
            answer=answer,
            analytics=analytics,
            evidence=self._build_evidence(
                work_item_ids,
                tools_used,
                filters_applied,
                worklog_count,
            ),
            context=conversation.context,
            conversation_id=conversation.conversation_id,
        )

    # -- evidence ---------------------------------------------------------

    def _build_evidence(
        self,
        work_item_ids: list[int],
        tools_used: list[str],
        filters_applied: dict[str, Any],
        worklog_count: int | None,
    ) -> Evidence:
        ids = _dedupe(work_item_ids)

        items: list[EvidenceItem] = []

        if ids:
            repo = AnalyticsRepository(
                self.session
            )

            for wid in ids[:25]:
                detail = repo.get_work_item(wid)

                items.append(
                    EvidenceItem(
                        work_item_id=wid,
                        title=(detail or {}).get(
                            "title"
                        ),
                    )
                )

        return Evidence(
            work_item_ids=ids,
            work_items=items,
            worklog_count=worklog_count,
            filters_applied=filters_applied,
            tools_used=_dedupe_str(
                tools_used
            ),
        )

    # -- non-tool responses -----------------------------------------------

    def _context_note(
        self,
        conversation: Conversation,
    ) -> str:
        active = conversation.context.model_dump(
            exclude_none=True,
            exclude={"last_work_item_ids"},
        )

        if not active:
            return (
                "No filters are currently carried over from earlier "
                "in this conversation."
            )

        pairs = ", ".join(
            f"{k}={v}"
            for k, v in active.items()
        )

        return (
            "Filters carried over from earlier in this conversation: "
            f"{pairs}. Follow-up questions such as 'what about QA?' "
            "should keep these unless the user changes them. Tools "
            "apply them automatically; pass only what the user has "
            "newly specified."
        )

    def _refusal(
        self,
        conversation: Conversation,
        message: str,
        intent: IntentResult,
    ) -> ChatResponse:
        answer = (
            f"I can't answer that from this data - it {intent.reason}. "
            "This dataset covers hours logged against Azure DevOps "
            "work items: who logged them, when, against which work "
            "item, under which memo and time code, and which product "
            "capability the work item was classified into. It holds "
            "no estimates, remaining work, dates, costs or quality "
            "signals, so any answer here would be guesswork."
        )

        conversation.add_turn(
            "user",
            message,
        )

        conversation.add_turn(
            "assistant",
            answer,
        )

        self.store.save(
            conversation
        )

        return ChatResponse(
            answer=answer,
            conversation_id=conversation.conversation_id,
            context=conversation.context,
            unsupported=True,
        )

    def _clarification(
        self,
        conversation: Conversation,
        message: str,
        intent: IntentResult,
    ) -> ChatResponse:
        answer = (
            f"Before I pull the numbers - {intent.reason}"
        )

        conversation.add_turn(
            "user",
            message,
        )

        conversation.add_turn(
            "assistant",
            answer,
        )

        self.store.save(
            conversation
        )

        return ChatResponse(
            answer=answer,
            conversation_id=conversation.conversation_id,
            context=conversation.context,
            needs_clarification=True,
        )

    def _plain(
        self,
        conversation: Conversation,
        answer: str,
    ) -> ChatResponse:
        return ChatResponse(
            answer=answer,
            conversation_id=conversation.conversation_id,
            context=conversation.context,
        )


# --- helpers ---------------------------------------------------------------


def _dedupe(values: list[int]) -> list[int]:
    seen: dict[int, None] = {}

    for v in values:
        seen.setdefault(v, None)

    return list(seen)


def _dedupe_str(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}

    for v in values:
        seen.setdefault(v, None)

    return list(seen)


def _extract_worklog_count(
    result: ToolResult,
) -> int | None:
    if isinstance(result.data, dict):
        value = result.data.get(
            "worklog_count"
        )

        if isinstance(value, int):
            return value

    return None


__all__ = [
    "ProductIntelligenceAgent",
    "TOOLS",
]