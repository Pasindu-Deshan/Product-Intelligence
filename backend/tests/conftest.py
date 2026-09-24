"""Shared test fixtures.

Repository/API tests need a real PostgreSQL database (the analytics layer uses
PostgreSQL-specific constructs: ``date_trunc``, ``FILTER (WHERE ...)``, ``ILIKE``).
They are skipped unless ``TEST_DATABASE_URL`` is set, so the pure unit tests
still run anywhere.

    export TEST_DATABASE_URL=postgresql+psycopg://pi:pi@localhost:5432/pi_test
    ./scripts/init_test_db.sh
    pytest
"""

from __future__ import annotations

import os
import pathlib

import pytest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "database"

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"
)

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL or "postgresql+psycopg://u:p@localhost/none")


@pytest.fixture(scope="session")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    from sqlalchemy import create_engine, text

    eng = create_engine(TEST_DATABASE_URL, future=True)
    with eng.begin() as conn:
        for name in sorted((MIGRATIONS / "migrations").glob("0*.sql")):
            if name.name.startswith("008"):
                continue  # role management needs superuser; not part of data tests
            conn.execute(text(name.read_text()))
        conn.execute(text((MIGRATIONS / "seed" / "dev_seed.sql").read_text()))
    return eng


@pytest.fixture
def session(engine):
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        yield s


@pytest.fixture
def service(session):
    from app.analytics.service import AnalyticsService

    return AnalyticsService(session)


class FakeLLM:
    """Scripted LLM stand-in.

    Tests assert on tool selection, parameter extraction and grounding, none of
    which should depend on a live model. ``responses`` is a list of
    ``LLMResponse`` objects returned in order.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.enabled = True

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools})
        if kwargs.get("response_format"):
            # Intent-extraction probe, not part of the scripted agent turn.
            # Returning empty JSON makes the caller fall back to its
            # deterministic path without consuming a scripted response.
            from app.agent.llm import LLMResponse

            return LLMResponse(content="{}")
        if not self.responses:
            from app.agent.llm import LLMResponse

            return LLMResponse(content="No further steps.")
        return self.responses.pop(0)


@pytest.fixture
def fake_llm():
    return FakeLLM
