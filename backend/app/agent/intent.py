"""Structured intent detection.

Two jobs, both done before the tool-calling loop runs:

1. **Guardrail.** Recognise questions the dataset cannot answer (forecasts,
   individual performance judgements) and questions too ambiguous to act on,
   so the agent refuses or clarifies instead of producing something plausible.
2. **Structure.** Produce a typed ``IntentResult`` used for evaluation scoring
   and logging, so intent accuracy is measurable rather than anecdotal.

The deterministic pass runs first and is cheap. The LLM pass is a fallback for
anything the patterns do not cover, and its output is validated into the same
closed enum - free-form model output is never trusted directly.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, get_args

from app.agent.llm import LLMClient, LLMError
from app.schemas.agent import Intent

logger = logging.getLogger(__name__)

VALID_INTENTS: frozenset[str] = frozenset(get_args(Intent))


@dataclass
class IntentResult:
    intent: Intent
    filters: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    confidence: float = 0.0

    @property
    def blocks_tool_use(self) -> bool:
        return self.intent in {"UNSUPPORTED", "CLARIFICATION_NEEDED"}


# --- deterministic guardrails ---------------------------------------------

# Questions about the future, or about how "good" someone or something is, are
# outside what logged hours can answer. Matching these in code (not in the
# prompt alone) means the refusal does not depend on model compliance.
_UNSUPPORTED_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(will|won't|going to)\b.*\b(finish|complete|deliver|ship|be done|hit)\b",
     "asks for a delivery forecast"),
    (r"\b(forecast|predict|projection|estimate to complete|etc?a)\b",
     "asks for a prediction"),
    (r"\b(on track|on time|behind schedule|ahead of schedule)\b",
     "asks for a schedule judgement"),
    (r"\b(who is|who's|which developer is)\b.*\b(best|worst|fastest|slowest|most productive|least productive|underperform)\b",
     "asks for an individual performance judgement"),
    (r"\b(performance review|rank(ing)? the team|rate the team|who should we (fire|promote))\b",
     "asks for a personnel judgement"),
    (r"\b(code quality|technical debt|how good is|bug rate per developer)\b",
     "asks about something not recorded in time logs"),
    (r"\b(budget|cost|revenue|invoice|billing rate|salary)\b",
     "asks about financial data that is not in this dataset"),
)

# A bare superlative with no metric named: "what took the most time" could mean
# work item, capability, user or type. Answering one of them silently is worse
# than asking.
_AMBIGUOUS_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^\s*(what|which)\s+(took|takes|consumed|used)\s+the\s+most\s*\??\s*$",
     "the most of what - work items, capabilities, people or work item types?"),
    (r"^\s*(what|which)\s+(is|was)\s+the\s+biggest\s*\??\s*$",
     "biggest by which measure?"),
    (r"^\s*how\s+(are|is)\s+(we|it|things)\s+doing\s*\??\s*$",
     "which measure would you like - total hours, effort by capability, or something else?"),
)

_INTENT_PATTERNS: tuple[tuple[str, Intent], ...] = (
    (r"\bdata quality|missing work item|duplicate|orphan|sync fail", "DATA_QUALITY"),
    (r"\bcompare\b|\bversus\b|\bvs\.?\b|difference between", "COMPARISON"),
    (r"\b(which|what|show|list).*(ticket|work item|item|story|bug).*(most|top|behind|contribut)", "WORK_ITEM_HOURS"),
    (r"\bwork items? (behind|for|contributing)", "CAPABILITY_WORK_ITEMS"),
    (r"\bcapabilit", "CAPABILITY_HOURS"),
    (r"\b(sprint|iteration)\b.*\bsummar", "ITERATION_SUMMARY"),
    (r"\bwork item \d+|\bticket \d+|#\d+", "WORK_ITEM_DETAIL"),
    (r"\b(qa|testing|development|dev|code review|support)\b", "MEMO_HOURS"),
    (r"\bovertime\b|\btime code\b", "TIME_CODE_HOURS"),
    (r"\b(per|by|each) (user|person|developer)\b|\bdid \w+ log\b|\bwho logged\b", "USER_HOURS"),
    (r"\b(bug|user story|task)s?\b.*\bhours?\b|\bhours?\b.*\bbugs?\b", "WORK_ITEM_TYPE_HOURS"),
    (r"\bper day\b|\bdaily\b|\bweekly\b|\bmonthly\b|\bover time\b|\btrend\b", "DATE_HOURS"),
    (r"\bhow (many|much) (hours|time)\b|\btotal\b", "TOTAL_HOURS"),
)

INTENT_EXTRACTION_PROMPT = """\
Classify the user's question into exactly one intent from this list:
{intents}

Also extract any filters you can identify. Use null where unknown.

Respond with JSON only:
{{"intent": "<one of the listed intents>",
  "filters": {{"iteration": null, "capability": null, "memo_code": null,
               "time_code": null, "user_id": null, "work_item_id": null,
               "work_item_type": null, "relative_range": null}},
  "confidence": <0 to 1>}}

Use CLARIFICATION_NEEDED when the question could reasonably mean two different
metrics. Use UNSUPPORTED when it asks for a prediction, a judgement of people
or quality, or data outside logged hours and work-item metadata.
"""


def detect_intent(message: str, llm: LLMClient | None = None) -> IntentResult:
    """Deterministic first, model second."""
    text = message.strip().lower()

    for pattern, reason in _UNSUPPORTED_PATTERNS:
        if re.search(pattern, text):
            return IntentResult(intent="UNSUPPORTED", reason=reason, confidence=1.0)

    for pattern, question in _AMBIGUOUS_PATTERNS:
        if re.search(pattern, text):
            return IntentResult(
                intent="CLARIFICATION_NEEDED", reason=question, confidence=1.0
            )

    for pattern, intent in _INTENT_PATTERNS:
        if re.search(pattern, text):
            return IntentResult(intent=intent, confidence=0.7, reason="pattern match")

    if llm is not None and llm.enabled:
        result = _llm_intent(message, llm)
        if result is not None:
            return result

    # Safe default: the tool-calling loop can still resolve it, and the model is
    # instructed to ask rather than guess.
    return IntentResult(intent="TOTAL_HOURS", confidence=0.2, reason="fallback")


def _llm_intent(message: str, llm: LLMClient) -> IntentResult | None:
    try:
        response = llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": INTENT_EXTRACTION_PROMPT.format(
                        intents="\n".join(f"- {i}" for i in sorted(VALID_INTENTS))
                    ),
                },
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.content or "{}")
    except (LLMError, json.JSONDecodeError):
        logger.debug("LLM intent extraction unavailable; using fallback", exc_info=True)
        return None

    intent = parsed.get("intent")
    if intent not in VALID_INTENTS:
        logger.info("Discarding out-of-vocabulary intent %r", intent)
        return None

    filters = parsed.get("filters") or {}
    return IntentResult(
        intent=intent,  # type: ignore[arg-type]
        filters={k: v for k, v in filters.items() if v is not None},
        confidence=float(parsed.get("confidence") or 0.5),
        reason="llm",
    )
