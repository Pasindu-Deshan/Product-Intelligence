"""Capability taxonomy loading and validation.

The taxonomy lives in the database (``capability`` / ``sub_capability``), not in
code, so it can be curated without a deploy. This module is the only place that
decides whether a proposed classification is acceptable — the classifier never
writes a label that has not passed through ``Taxonomy.validate``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.database.repositories import AnalyticsRepository

logger = logging.getLogger(__name__)

UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class TaxonomyEntry:
    capability: str
    description: str | None
    sub_capabilities: tuple[str, ...] = field(default_factory=tuple)


class Taxonomy:
    """An immutable snapshot of the approved capability list."""

    def __init__(self, entries: list[TaxonomyEntry]) -> None:
        self._entries = {e.capability: e for e in entries}

    @classmethod
    def load(cls, session: Session) -> "Taxonomy":
        rows = AnalyticsRepository(session).load_taxonomy()
        grouped: dict[str, dict] = {}
        for row in rows:
            entry = grouped.setdefault(
                row["capability"],
                {"description": row.get("capability_description"), "subs": []},
            )
            if row.get("sub_capability"):
                entry["subs"].append(row["sub_capability"])
        return cls(
            [
                TaxonomyEntry(
                    capability=name,
                    description=data["description"],
                    sub_capabilities=tuple(data["subs"]),
                )
                for name, data in sorted(grouped.items())
            ]
        )

    # -- access ----------------------------------------------------------

    @property
    def capabilities(self) -> list[str]:
        return list(self._entries)

    def sub_capabilities(self, capability: str) -> list[str]:
        entry = self._entries.get(capability)
        return list(entry.sub_capabilities) if entry else []

    def is_empty(self) -> bool:
        return not self._entries

    # -- validation ------------------------------------------------------

    def validate(
        self, capability: str | None, sub_capability: str | None = None
    ) -> tuple[str | None, str | None, str | None]:
        """Return ``(capability, sub_capability, rejection_reason)``.

        An invented capability is rejected outright rather than being created.
        An invented sub-capability is dropped but the parent capability is kept,
        because the coarser label is still useful and still approved.
        """
        if not capability or capability == UNCLASSIFIED:
            return None, None, "classifier declined to classify"

        match = self._case_insensitive(capability)
        if match is None:
            return None, None, (
                f"'{capability}' is not in the approved taxonomy; "
                "classification rejected"
            )

        if not sub_capability:
            return match, None, None

        subs = {s.lower(): s for s in self.sub_capabilities(match)}
        canonical_sub = subs.get(sub_capability.strip().lower())
        if canonical_sub is None:
            logger.info(
                "Dropping unapproved sub-capability %r under %r", sub_capability, match
            )
            return match, None, None
        return match, canonical_sub, None

    def _case_insensitive(self, name: str) -> str | None:
        target = name.strip().lower()
        for known in self._entries:
            if known.lower() == target:
                return known
        return None

    # -- prompt rendering ------------------------------------------------

    def as_prompt_block(self) -> str:
        """The exact, closed list handed to the model. Keeping this generated
        from the database guarantees the prompt and the constraint agree."""
        lines: list[str] = []
        for entry in self._entries.values():
            desc = f" - {entry.description}" if entry.description else ""
            lines.append(f"- {entry.capability}{desc}")
            for sub in entry.sub_capabilities:
                lines.append(f"    - {sub}")
        return "\n".join(lines)
