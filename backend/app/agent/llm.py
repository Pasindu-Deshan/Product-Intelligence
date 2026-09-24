"""Thin LLM client.

Isolated here so that no other module imports an SDK or knows about message
formats. Targets any OpenAI-compatible chat-completions endpoint that supports
tool/function calling (OpenAI, Azure OpenAI via its compatible route, etc.).

Swapping providers means replacing this file only.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the model is unreachable or returns an unusable response."""


class LLMNotConfigured(LLMError):
    """Raised when no API key is configured; callers degrade gracefully."""


class LLMRateLimitError(LLMError):
    """Raised when the LLM provider rejects a request due to rate limiting/quota."""

    def __init__(
        self,
        message: str = "The language model usage limit has been reached.",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


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
        """Send a chat-completion request to the configured LLM provider."""

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

        url = (
            f"{self.settings.llm_api_base.rstrip('/')}"
            "/chat/completions"
        )

        try:
            with httpx.Client(
                timeout=self.settings.llm_timeout_seconds
            ) as client:
                resp = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.settings.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

        except httpx.HTTPError as exc:
            logger.exception("LLM transport error")

            raise LLMError(
                "The language model is currently unreachable."
            ) from exc

        # ---------------------------------------------------------------
        # HTTP 429 - Rate limit / quota exceeded
        # ---------------------------------------------------------------
        if resp.status_code == 429:
            retry_after = _extract_retry_after(resp)

            logger.warning(
                "LLM rate limit/quota exceeded. "
                "retry_after=%s response=%s",
                retry_after,
                resp.text[:1000],
            )

            message = (
                "The language model usage limit has been reached."
            )

            if retry_after is not None:
                message += (
                    f" Please retry in approximately "
                    f"{retry_after} seconds."
                )

            raise LLMRateLimitError(
                message=message,
                retry_after=retry_after,
            )

        # ---------------------------------------------------------------
        # Other HTTP errors
        # ---------------------------------------------------------------
        if resp.status_code >= 400:
            logger.error(
                "LLM returned HTTP %s: %s",
                resp.status_code,
                resp.text[:1000],
            )

            raise LLMError(
                "The language model returned an error."
            )

        # ---------------------------------------------------------------
        # Parse successful response
        # ---------------------------------------------------------------
        try:
            body = resp.json()
            message = body["choices"][0]["message"]

        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.exception(
                "Unexpected LLM response shape"
            )

            raise LLMError(
                "The language model returned an unexpected response."
            ) from exc

        # ---------------------------------------------------------------
        # Parse tool calls
        # ---------------------------------------------------------------
        tool_calls: list[ToolCall] = []

        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function") or {}

            tool_calls.append(
                ToolCall(
                    id=tool_call.get("id", ""),
                    name=function.get("name", ""),
                    arguments=_safe_json(
                        function.get("arguments")
                    ),
                )
            )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            raw_message=message,
        )


def _extract_retry_after(resp: httpx.Response) -> int | None:
    """Extract retry information from provider response.

    Providers may expose retry information in the Retry-After HTTP header.
    Gemini may also include text such as:

        "Please retry in 31.95s."

    Returns:
        Number of seconds to wait, or None if unavailable.
    """

    # ---------------------------------------------------------------
    # 1. Standard HTTP Retry-After header
    # ---------------------------------------------------------------
    header = resp.headers.get("Retry-After")

    if header:
        try:
            return max(1, int(float(header)))
        except (TypeError, ValueError):
            pass

    # ---------------------------------------------------------------
    # 2. Provider-specific response message
    # ---------------------------------------------------------------
    try:
        body = resp.json()

        error = body.get("error", {})

        if isinstance(error, dict):
            message = error.get("message", "")

            if isinstance(message, str):
                match = re.search(
                    r"retry\s+in\s+([\d.]+)\s*s",
                    message,
                    re.IGNORECASE,
                )

                if match:
                    return max(
                        1,
                        int(float(match.group(1))),
                    )

    except (ValueError, TypeError, AttributeError):
        pass

    return None


def _safe_json(raw: str | None) -> dict[str, Any]:
    """Models occasionally emit malformed argument JSON; treat that as 'no
    arguments' and let parameter validation produce a clear error.
    """

    if not raw:
        return {}

    try:
        parsed = json.loads(raw)

    except json.JSONDecodeError:
        logger.warning(
            "Could not parse tool arguments: %r",
            raw[:200],
        )
        return {}

    return parsed if isinstance(parsed, dict) else {}