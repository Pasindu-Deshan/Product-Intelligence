"""Conversational endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.agent.agent import ProductIntelligenceAgent
from app.api.deps import SessionDep
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, session: SessionDep) -> ChatResponse:
    """Ask a natural-language question.

    The response always carries the structured analytics and the evidence used
    to produce the answer, so the UI can show the user where a number came from.
    """
    return ProductIntelligenceAgent(session).ask(request)
