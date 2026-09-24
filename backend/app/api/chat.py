"""Conversational endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.agent.agent import ProductIntelligenceAgent
from app.agent.llm import LLMError, LLMRateLimitError
from app.api.deps import SessionDep
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, session: SessionDep) -> ChatResponse:
    """Ask a natural-language question.

    The response carries the structured analytics and evidence used to produce
    the answer, so the UI can show the user where a number came from.

    LLM infrastructure failures are translated into appropriate HTTP status
    codes while keeping dashboard and analytics APIs independent of the LLM.
    """
    try:
        return ProductIntelligenceAgent(session).ask(request)

    except LLMRateLimitError as exc:
        headers = {}

        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers=headers or None,
        ) from exc

    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
