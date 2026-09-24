"""Agent tests.

The model is always a scripted fake: we are testing our orchestration - intent
guardrails, tool selection, parameter extraction, grounding and follow-up
context - not the vendor's model.
"""

from __future__ import annotations

import json

import pytest

from app.agent.agent import ProductIntelligenceAgent
from app.agent.conversation import InMemoryConversationStore
from app.agent.intent import detect_intent
from app.agent.llm import LLMResponse, ToolCall
from app.schemas.agent import ChatRequest
from tests.conftest import requires_db


def _tool_turn(name: str, arguments: dict, call_id: str = "call-1") -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        raw_message={
            "role": "assistant",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        },
    )


# --- intent guardrails (no database, no model) ----------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Will this project finish on time?",
        "Are we on track for the release?",
        "Forecast the remaining effort",
        "Who is the best developer on the team?",
        "How much did this cost us?",
    ],
)
def test_unanswerable_questions_are_refused(question):
    assert detect_intent(question).intent == "UNSUPPORTED"


@pytest.mark.parametrize("question", ["What took the most?", "Which is the biggest?"])
def test_ambiguous_questions_ask_for_clarification(question):
    assert detect_intent(question).intent == "CLARIFICATION_NEEDED"


@pytest.mark.parametrize(
    "question,expected",
    [
        ("How many hours did we spend last sprint?", "TOTAL_HOURS"),
        ("How much time did we spend on QA?", "MEMO_HOURS"),
        ("Which tickets took the most time?", "WORK_ITEM_HOURS"),
        ("Which capabilities consumed the most development time?", "CAPABILITY_HOURS"),
        ("Compare Sprint 24 with Sprint 23.", "COMPARISON"),
        ("Show me the data quality issues", "DATA_QUALITY"),
    ],
)
def test_intent_detection(question, expected):
    assert detect_intent(question).intent == expected


@requires_db
def test_refusal_does_not_call_any_tool(session, fake_llm):
    llm = fake_llm([])
    agent = ProductIntelligenceAgent(session, llm=llm, store=InMemoryConversationStore())
    response = agent.ask(ChatRequest(message="Will this project finish on time?"))
    assert response.unsupported is True
    assert response.analytics == {}
    assert llm.calls == []  # no model round-trip at all


@requires_db
def test_clarification_is_a_question_not_a_guess(session, fake_llm):
    agent = ProductIntelligenceAgent(
        session, llm=fake_llm([]), store=InMemoryConversationStore()
    )
    response = agent.ask(ChatRequest(message="What took the most?"))
    assert response.needs_clarification is True
    assert "?" in response.answer


# --- grounded answers ------------------------------------------------------


@requires_db
def test_answer_is_grounded_in_tool_output(session, fake_llm):
    llm = fake_llm([
        _tool_turn("get_time_summary", {"capability": "Authentication"}),
        LLMResponse(content="Authentication accounted for 43.5 hours."),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=InMemoryConversationStore())
    response = agent.ask(
        ChatRequest(message="How much time did we spend on Authentication?")
    )
    assert response.analytics["get_time_summary"]["total_hours"] == pytest.approx(43.5)
    assert response.evidence.tools_used == ["get_time_summary"]
    assert response.evidence.filters_applied == {"capability": "Authentication"}


@requires_db
def test_evidence_includes_work_item_ids_and_titles(session, fake_llm):
    llm = fake_llm([
        _tool_turn("get_work_items_by_capability", {"capability": "Authentication"}),
        LLMResponse(content="Three work items contributed."),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=InMemoryConversationStore())
    response = agent.ask(ChatRequest(message="Show me the tickets behind Authentication"))
    assert set(response.evidence.work_item_ids) == {1234, 1250, 1288}
    titles = {i.title for i in response.evidence.work_items}
    assert "Implement SSO" in titles


@requires_db
def test_tool_error_is_surfaced_to_the_model_not_swallowed(session, fake_llm):
    llm = fake_llm([
        _tool_turn("get_work_item_details", {"work_item_id": 424242}),
        LLMResponse(content="I couldn't find that work item."),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=InMemoryConversationStore())
    response = agent.ask(ChatRequest(message="Tell me about work item 424242"))
    assert response.analytics == {}  # failed tools contribute no analytics
    tool_messages = [
        m for call in llm.calls for m in call["messages"] if m.get("role") == "tool"
    ]
    assert any('"ok":false' in m["content"] for m in tool_messages)


# --- conversational context ------------------------------------------------


@requires_db
def test_follow_up_inherits_previous_filters(session, fake_llm):
    store = InMemoryConversationStore()
    llm = fake_llm([
        _tool_turn("get_time_summary", {"capability": "Authentication"}),
        LLMResponse(content="43.5 hours."),
        _tool_turn("get_time_summary", {"memo_code": "QA"}, call_id="call-2"),
        LLMResponse(content="7.0 hours of that was QA."),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=store)

    first = agent.ask(ChatRequest(message="How much time did we spend on Authentication?"))
    assert first.context.capability == "Authentication"

    second = agent.ask(
        ChatRequest(message="How much of that was QA?", conversation_id=first.conversation_id)
    )
    # The second tool call passed only memo_code; capability came from context.
    assert second.analytics["get_time_summary"]["total_hours"] == pytest.approx(7.0)
    assert second.context.capability == "Authentication"
    assert second.context.memo_code == "QA"


@requires_db
def test_reset_context_clears_carried_filters(session, fake_llm):
    store = InMemoryConversationStore()
    llm = fake_llm([
        _tool_turn("get_time_summary", {"capability": "Authentication"}),
        LLMResponse(content="43.5 hours."),
        _tool_turn("get_time_summary", {}, call_id="call-2"),
        LLMResponse(content="60.5 hours in total."),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=store)
    first = agent.ask(ChatRequest(message="Hours on Authentication?"))
    second = agent.ask(
        ChatRequest(
            message="How many hours in total?",
            conversation_id=first.conversation_id,
            reset_context=True,
        )
    )
    assert second.analytics["get_time_summary"]["total_hours"] == pytest.approx(60.5)


@requires_db
def test_context_is_offered_to_the_model_as_a_system_note(session, fake_llm):
    store = InMemoryConversationStore()
    llm = fake_llm([
        _tool_turn("get_time_summary", {"capability": "Scheduling"}),
        LLMResponse(content="15 hours."),
        LLMResponse(content="Anything else?"),
    ])
    agent = ProductIntelligenceAgent(session, llm=llm, store=store)
    first = agent.ask(ChatRequest(message="Hours on Scheduling?"))
    agent.ask(ChatRequest(message="thanks", conversation_id=first.conversation_id))
    last_system = [
        m for m in llm.calls[-1]["messages"] if m.get("role") == "system"
    ][-1]["content"]
    assert "Scheduling" in last_system


@requires_db
def test_iteration_limit_is_enforced(session, fake_llm):
    """A model that keeps calling tools must not loop forever."""
    llm = fake_llm([_tool_turn("get_time_summary", {}, f"c{i}") for i in range(20)])
    agent = ProductIntelligenceAgent(session, llm=llm, store=InMemoryConversationStore())
    response = agent.ask(ChatRequest(message="How many hours?"))
    assert len(llm.calls) <= agent.settings.llm_max_tool_iterations
    assert "more specific" in response.answer


@requires_db
def test_llm_outage_degrades_gracefully(session):
    from app.agent.llm import LLMError

    class BrokenLLM:
        enabled = True

        def chat(self, *args, **kwargs):
            raise LLMError("upstream down")

    agent = ProductIntelligenceAgent(
        session, llm=BrokenLLM(), store=InMemoryConversationStore()
    )
    response = agent.ask(ChatRequest(message="How many hours did we log?"))
    assert "dashboard" in response.answer.lower()
    assert response.analytics == {}
