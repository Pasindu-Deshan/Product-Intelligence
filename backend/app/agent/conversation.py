"""Conversation state.

We keep two things per conversation:

* a **structured context** (resolved filters) - this is what makes "how much of
  that was QA?" work, by merging a new filter over the previous one rather than
  re-deriving intent from the transcript;
* a **short transcript window** - enough for the model to resolve pronouns,
  capped so prompts stay small and old turns cannot skew a new question.

Tool results are deliberately NOT retained beyond the turn that produced them.
Every answer re-queries the database, so a stale number can never be recycled.

The in-memory store is fine for a single instance. For multi-instance Azure
deployments, swap ``InMemoryConversationStore`` for a Redis-backed one
implementing the same three methods.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.schemas.agent import ConversationContext

MAX_TRANSCRIPT_TURNS = 6
CONVERSATION_TTL = timedelta(hours=2)


@dataclass
class Conversation:
    conversation_id: str
    context: ConversationContext = field(default_factory=ConversationContext)
    transcript: deque[dict[str, str]] = field(
        default_factory=lambda: deque(maxlen=MAX_TRANSCRIPT_TURNS * 2)
    )
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_turn(self, role: str, content: str) -> None:
        self.transcript.append({"role": role, "content": content})
        self.updated_at = datetime.now(timezone.utc)

    def messages(self) -> list[dict[str, str]]:
        return list(self.transcript)

    def apply_context(self, updates: dict[str, Any]) -> None:
        self.context = self.context.merge(updates)
        self.updated_at = datetime.now(timezone.utc)

    def reset_context(self) -> None:
        self.context = ConversationContext()


class ConversationStore(Protocol):
    def get_or_create(self, conversation_id: str | None) -> Conversation: ...
    def save(self, conversation: Conversation) -> None: ...
    def purge_expired(self) -> int: ...


class InMemoryConversationStore:
    def __init__(self, ttl: timedelta = CONVERSATION_TTL) -> None:
        self._data: dict[str, Conversation] = {}
        self._ttl = ttl
        self._lock = threading.Lock()

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        with self._lock:
            self._purge_locked()
            if conversation_id and conversation_id in self._data:
                return self._data[conversation_id]
            new_id = conversation_id or str(uuid.uuid4())
            conversation = Conversation(conversation_id=new_id)
            self._data[new_id] = conversation
            return conversation

    def save(self, conversation: Conversation) -> None:
        with self._lock:
            self._data[conversation.conversation_id] = conversation

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_locked()

    def _purge_locked(self) -> int:
        cutoff = datetime.now(timezone.utc) - self._ttl
        stale = [k for k, v in self._data.items() if v.updated_at < cutoff]
        for key in stale:
            del self._data[key]
        return len(stale)


conversation_store: ConversationStore = InMemoryConversationStore()
