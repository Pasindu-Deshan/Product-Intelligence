"""Application configuration. All values come from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Nothing here has a credential-bearing default. Missing required secrets
    fail fast at startup rather than silently falling back to something weak.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "Product Intelligence"
    environment: Literal["local", "dev", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Database ----------------------------------------------------------
    # READ-ONLY connection used by the API, analytics layer and agent tools.
    database_url: str = Field(
        ...,
        description="postgresql+psycopg://user:pass@host/db",
    )

    # Separate, narrower connection used only by the capability classifier,
    # which is the one component allowed to write work_item_capability.
    classifier_database_url: str | None = None

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_statement_timeout_ms: int = 15_000

    # --- LLM ---------------------------------------------------------------
    # Generic LLM configuration so the application is not tightly coupled
    # to a specific provider.
    #
    # For local testing with Gemini:
    #
    #   LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/
    #   LLM_API_KEY=<Gemini API key>
    #   LLM_MODEL=<Gemini model>
    #
    # The provider can later be changed to Azure OpenAI or another
    # OpenAI-compatible provider without changing the agent architecture.
    llm_api_base: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    llm_api_key: str | None = None
    llm_model: str = "gemini-3-flash-preview"
    llm_timeout_seconds: int = 45
    llm_max_tool_iterations: int = 5

    # Written into work_item_capability.model_version so classifications are
    # traceable to the exact model + prompt revision that produced them.
    classifier_model_version: str = "pi-classifier-v1"
    classifier_min_confidence: float = 0.60

    # --- Query safety ------------------------------------------------------
    max_rows_default: int = 50
    max_rows_hard_limit: int = 500

    # --- Auth (placeholder for Entra ID) -----------------------------------
    auth_enabled: bool = False
    auth_tenant_id: str | None = None
    auth_client_id: str | None = None
    auth_audience: str | None = None

    @field_validator("database_url", "classifier_database_url")
    @classmethod
    def _require_driver(cls, v: str | None) -> str | None:
        if v and v.startswith("postgres://"):
            # Normalise the Heroku/Azure-style URL SQLAlchemy 2 rejects.
            return v.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )
        return v

    @property
    def llm_enabled(self) -> bool:
        """Return True when an LLM API key has been configured."""
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]