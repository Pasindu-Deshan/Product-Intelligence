"""Thin LLM client.

Isolated here so that no other module imports an SDK or knows about message
formats. Targets any OpenAI-compatible chat-completions endpoint that supports
tool/function calling (OpenAI, Azure OpenAI via its compatible route, etc.).

Swapping providers means replacing this file only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the model is unreachable or returns an unusable response."""


class LLMNotConfigured(LLMError):
    """Raised when no API key is configured; callers degrade gracefully."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    def __init__(self, settings=None) -> None:
        self.settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self.enabled:
            raise LLMNotConfigured(
                "LLM_API_KEY is not set. Conversational features are disabled; "
                "the dashboard and analytics APIs continue to work."
            )

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format

        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                resp = client.post(
                    f"{self.settings.llm_api_base.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            # Never let provider detail (which can contain the key in a URL)
            # bubble up to the API surface.
            logger.exception("LLM transport error")
            raise LLMError("The language model is currently unreachable.") from exc

        if resp.status_code >= 400:
            logger.error("LLM returned %s: %s", resp.status_code, resp.text[:500])
            raise LLMError("The language model returned an error.")

        try:
            message = resp.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.exception("Unexpected LLM response shape")
            raise LLMError("The language model returned an unexpected response.") from exc

        return LLMResponse(
            content=message.get("content"),
            tool_calls=[
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=_safe_json(tc["function"].get("arguments")),
                )
                for tc in message.get("tool_calls") or []
            ],
            raw_message=message,
        )


def _safe_json(raw: str | None) -> dict[str, Any]:
    """Models occasionally emit malformed argument JSON; treat that as 'no
    arguments' and let parameter validation produce a clear error."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Could not parse tool arguments: %r", raw[:200])
        return {}
    return parsed if isinstance(parsed, dict) else {}
