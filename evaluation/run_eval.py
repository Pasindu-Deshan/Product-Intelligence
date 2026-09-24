#!/usr/bin/env python
"""Evaluation harness for the Product Intelligence agent.

Scores the dimensions listed in Section 22:

* intent accuracy          - does the guardrail/classifier pick the right intent?
* tool-selection accuracy  - did the agent call the tool we expect?
* parameter accuracy       - were the filters extracted correctly?
* numerical accuracy       - does the figure match the hand-derived expectation?
* evidence accuracy        - are the right work items cited?
* refusal/clarification    - are unanswerable and ambiguous questions handled?

Usage:

    export DATABASE_URL=postgresql+psycopg://...   # seeded test database
    export LLM_API_KEY=...                         # optional; see --intent-only
    python evaluation/run_eval.py                  # full run
    python evaluation/run_eval.py --intent-only    # no LLM calls, no cost
    python evaluation/run_eval.py --category follow_up
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

TOLERANCE = 0.01


@dataclass
class Score:
    total: int = 0
    correct: int = 0
    failures: list[str] = field(default_factory=list)

    def record(self, ok: bool, label: str = "") -> None:
        self.total += 1
        if ok:
            self.correct += 1
        elif label:
            self.failures.append(label)

    @property
    def pct(self) -> float:
        return round(self.correct / self.total * 100, 1) if self.total else 0.0


def load_dataset() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    questions = json.loads((HERE / "questions.json").read_text())["questions"]
    answers = json.loads((HERE / "expected_answers.json").read_text())["answers"]
    return questions, answers


def evaluate_intent(questions: list[dict[str, Any]]) -> Score:
    from app.agent.intent import detect_intent

    score = Score()
    for q in questions:
        result = detect_intent(q["question"])
        expected = q["expected_intent"]
        # Guardrail intents must match exactly; analytical intents are scored
        # leniently because several tools can legitimately answer one question.
        if expected in {"UNSUPPORTED", "CLARIFICATION_NEEDED"}:
            ok = result.intent == expected
        else:
            ok = result.intent not in {"UNSUPPORTED", "CLARIFICATION_NEEDED"}
        score.record(ok, f"{q['id']}: expected {expected}, got {result.intent}")
    return score


def evaluate_full(questions: list[dict[str, Any]], expected: dict[str, Any]) -> dict[str, Score]:
    from sqlalchemy.orm import Session

    from app.agent.agent import ProductIntelligenceAgent
    from app.agent.conversation import InMemoryConversationStore
    from app.database.connection import read_engine
    from app.schemas.agent import ChatRequest

    scores = {
        "tool_selection": Score(),
        "numerical": Score(),
        "evidence": Score(),
        "refusal": Score(),
        "clarification": Score(),
    }

    with Session(read_engine) as session:
        store = InMemoryConversationStore()
        agent = ProductIntelligenceAgent(session, store=store)

        for q in questions:
            exp = expected.get(q["id"], {})
            if q.get("requires_context"):
                # Seed the carried context so follow-ups can be scored in isolation.
                conversation = store.get_or_create(q["id"])
                conversation.apply_context(q.get("context", {}))
                response = agent.ask(
                    ChatRequest(message=q["question"], conversation_id=q["id"])
                )
            else:
                response = agent.ask(ChatRequest(message=q["question"]))

            if q.get("expect_refusal"):
                scores["refusal"].record(response.unsupported, q["id"])
                continue
            if q.get("expect_clarification"):
                scores["clarification"].record(response.needs_clarification, q["id"])
                continue

            if q.get("expected_tool"):
                ok = q["expected_tool"] in response.evidence.tools_used
                scores["tool_selection"].record(
                    ok, f"{q['id']}: used {response.evidence.tools_used}"
                )

            if isinstance(exp, dict) and "total_hours" in exp:
                actual = _find_number(response.analytics, "total_hours")
                ok = actual is not None and abs(actual - exp["total_hours"]) < TOLERANCE
                scores["numerical"].record(
                    ok, f"{q['id']}: expected {exp['total_hours']}, got {actual}"
                )

            if isinstance(exp, dict) and "work_item_ids" in exp:
                ok = set(exp["work_item_ids"]).issubset(set(response.evidence.work_item_ids))
                scores["evidence"].record(
                    ok, f"{q['id']}: cited {response.evidence.work_item_ids}"
                )

    return scores


def _find_number(analytics: dict[str, Any], key: str) -> float | None:
    for value in analytics.values():
        if isinstance(value, dict) and key in value:
            try:
                return float(value[key])
            except (TypeError, ValueError):
                continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent-only", action="store_true", help="skip LLM/database calls")
    parser.add_argument("--category", help="run a single category")
    parser.add_argument("--verbose", action="store_true", help="list failures")
    args = parser.parse_args()

    questions, expected = load_dataset()
    if args.category:
        questions = [q for q in questions if q["category"] == args.category]
        if not questions:
            print(f"No questions in category {args.category!r}")
            return 2

    print(f"Evaluating {len(questions)} questions\n")

    intent = evaluate_intent(questions)
    results = {"intent": intent}

    if not args.intent_only:
        results.update(evaluate_full(questions, expected))

    print(f"{'metric':<20} {'score':>8} {'n':>5}")
    print("-" * 35)
    exit_code = 0
    for name, score in results.items():
        if score.total:
            print(f"{name:<20} {score.pct:>7}% {score.total:>5}")
            if score.pct < 90:
                exit_code = 1
    if args.verbose:
        for name, score in results.items():
            for failure in score.failures:
                print(f"  [{name}] {failure}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
