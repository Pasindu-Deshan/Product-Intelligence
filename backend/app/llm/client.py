"""Provider-independent LLM client."""

from __future__ import annotations

from google import genai

from app.config import get_settings


class LLMClient:
    """Application-level interface to the configured LLM provider."""

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.llm_api_key:
            raise RuntimeError(
                "LLM_API_KEY is not configured."
            )

        self._model = settings.llm_model
        self._client = genai.Client(
            api_key=settings.llm_api_key
        )

    def generate(self, prompt: str) -> str:
        """Generate a text response."""

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )

        if not response.text:
            raise RuntimeError("LLM returned an empty response.")

        return response.text


def get_llm_client() -> LLMClient:
    """Return a configured LLM client."""
    return LLMClient()