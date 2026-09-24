"""AI capability classifier.

Responsibilities and, just as importantly, non-responsibilities:

* It proposes a capability from a **closed** taxonomy. Anything outside that
  list is rejected by ``Taxonomy.validate``, not persisted.
* It returns a confidence score and records the model version.
* It abstains (``UNCLASSIFIED``) when the work item carries too little signal.
* It never touches analytics numbers. Hours are never seen or produced here.
* It is the only component that writes, and it does so through a separate,
  narrowly-privileged connection.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.llm import LLMClient, LLMError
from app.classification.taxonomy import UNCLASSIFIED, Taxonomy
from app.config import get_settings
from app.database.connection import classifier_session
from app.database.repositories import AnalyticsRepository

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """\
You classify Azure DevOps work items into a product capability taxonomy.

Rules:
1. You may ONLY choose a capability from the approved list provided. Never
   invent a new capability or sub-capability name.
2. If the work item does not clearly belong to any approved capability, or the
   title and description carry too little information to decide, return
   "UNCLASSIFIED". Abstaining is the correct answer in that case.
3. Return a confidence between 0 and 1 reflecting how certain you are.
4. Base your decision only on the work item title, description, type and the
   worklog comments supplied. Do not speculate about the product beyond them.
5. Respond with JSON only, matching the schema you are given.
"""

RESPONSE_SCHEMA_HINT = """\
Respond with exactly this JSON shape:
{"capability": "<approved capability name or UNCLASSIFIED>",
 "sub_capability": "<approved sub-capability name or null>",
 "confidence": <number between 0 and 1>,
 "reasoning": "<one short sentence>"}
"""


@dataclass
class ClassificationResult:
    work_item_id: int
    capability: str | None
    sub_capability: str | None
    confidence: float
    model_version: str
    reasoning: str | None = None
    rejected_reason: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.capability is not None

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < get_settings().classifier_min_confidence


class CapabilityClassifier:
    def __init__(
        self,
        read_session: Session,
        llm: LLMClient | None = None,
        settings=None,
    ) -> None:
        self.read_session = read_session
        self.repo = AnalyticsRepository(read_session)
        self.llm = llm or LLMClient()
        self.settings = settings or get_settings()
        self.taxonomy = Taxonomy.load(read_session)

    # -- single item ------------------------------------------------------

    def classify_work_item(self, work_item_id: int) -> ClassificationResult:
        item = self.repo.get_work_item(work_item_id)
        if item is None:
            return ClassificationResult(
                work_item_id=work_item_id,
                capability=None,
                sub_capability=None,
                confidence=0.0,
                model_version=self.settings.classifier_model_version,
                rejected_reason="work item not found",
            )
        if self.taxonomy.is_empty():
            return ClassificationResult(
                work_item_id=work_item_id,
                capability=None,
                sub_capability=None,
                confidence=0.0,
                model_version=self.settings.classifier_model_version,
                rejected_reason="taxonomy is empty; populate the capability table first",
            )

        comments = self._sample_comments(work_item_id)
        if not self._has_enough_signal(item, comments):
            return ClassificationResult(
                work_item_id=work_item_id,
                capability=None,
                sub_capability=None,
                confidence=0.0,
                model_version=self.settings.classifier_model_version,
                rejected_reason="insufficient information to classify",
            )

        try:
            raw = self._ask_model(item, comments)
        except LLMError as exc:
            logger.warning("Classification failed for %s: %s", work_item_id, exc)
            return ClassificationResult(
                work_item_id=work_item_id,
                capability=None,
                sub_capability=None,
                confidence=0.0,
                model_version=self.settings.classifier_model_version,
                rejected_reason=str(exc),
            )

        capability, sub_capability, rejection = self.taxonomy.validate(
            raw.get("capability"), raw.get("sub_capability")
        )
        confidence = _clamp_confidence(raw.get("confidence"))
        if rejection:
            confidence = 0.0

        return ClassificationResult(
            work_item_id=work_item_id,
            capability=capability,
            sub_capability=sub_capability,
            confidence=confidence,
            model_version=self.settings.classifier_model_version,
            reasoning=(raw.get("reasoning") or None),
            rejected_reason=rejection,
        )

    # -- batch ------------------------------------------------------------

    def classify_pending(self, limit: int = 25) -> list[ClassificationResult]:
        """Classify items that are new, stale, or classified by an older model.
        Human-reviewed classifications are never overwritten."""
        pending = self.repo.work_items_needing_classification(
            limit=limit, model_version=self.settings.classifier_model_version
        )
        results = []
        for row in pending:
            result = self.classify_work_item(int(row["work_item_id"]))
            if result.is_usable:
                self.persist(result)
            results.append(result)
        return results

    # -- persistence ------------------------------------------------------

    def persist(self, result: ClassificationResult) -> None:
        """Upsert into work_item_capability via the write-capable connection.

        Rows a human has reviewed are left untouched: the WHERE clause on the
        DO UPDATE branch means a re-run cannot silently undo a correction.
        """
        if not result.is_usable:
            logger.info(
                "Not persisting work item %s: %s",
                result.work_item_id,
                result.rejected_reason,
            )
            return

        sql = text(
            """
            INSERT INTO work_item_capability
                (work_item_id, capability, sub_capability, confidence,
                 model_version, classified_date)
            VALUES
                (:work_item_id, :capability, :sub_capability, :confidence,
                 :model_version, :classified_date)
            ON CONFLICT (work_item_id, capability) DO UPDATE SET
                sub_capability  = EXCLUDED.sub_capability,
                confidence      = EXCLUDED.confidence,
                model_version   = EXCLUDED.model_version,
                classified_date = EXCLUDED.classified_date
            WHERE work_item_capability.is_human_reviewed = false
            """
        )
        with classifier_session() as session:
            session.execute(
                sql,
                {
                    "work_item_id": result.work_item_id,
                    "capability": result.capability,
                    "sub_capability": result.sub_capability,
                    "confidence": result.confidence,
                    "model_version": result.model_version,
                    "classified_date": datetime.now(timezone.utc),
                },
            )

    # -- internals --------------------------------------------------------

    def _sample_comments(self, work_item_id: int, limit: int = 10) -> list[str]:
        logs = self.repo.get_worklogs_for_work_item(work_item_id, limit=limit)
        return [c for c in (log.get("comment", "").strip() for log in logs) if c]

    @staticmethod
    def _has_enough_signal(item: dict[str, Any], comments: list[str]) -> bool:
        """Rule 7 of Section 8: don't classify on noise. A bare ID with no
        title, description or comments cannot be classified honestly."""
        title = (item.get("title") or "").strip()
        description = (item.get("description") or "").strip()
        if len(title) >= 10:
            return True
        if len(description) >= 20:
            return True
        return sum(len(c) for c in comments) >= 40

    def _ask_model(self, item: dict[str, Any], comments: list[str]) -> dict[str, Any]:
        user_content = (
            f"Approved taxonomy:\n{self.taxonomy.as_prompt_block()}\n\n"
            f"Work item:\n"
            f"  id: {item['work_item_id']}\n"
            f"  type: {item.get('work_item_type')}\n"
            f"  title: {item.get('title')}\n"
            f"  description: {(item.get('description') or '')[:2000]}\n"
            f"  area path: {item.get('area_path')}\n\n"
            f"Worklog comments:\n"
            + "\n".join(f"  - {c[:300]}" for c in comments[:10])
            + f"\n\n{RESPONSE_SCHEMA_HINT}"
        )
        response = self.llm.chat(
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(response.content or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError("Classifier returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise LLMError("Classifier returned an unexpected JSON type.")
        return parsed


def _clamp_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, round(conf, 4)))


__all__ = [
    "CapabilityClassifier",
    "ClassificationResult",
    "CLASSIFIER_SYSTEM_PROMPT",
    "UNCLASSIFIED",
]
