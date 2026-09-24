"""Database engine/session management.

Two engines, deliberately:

* ``read_engine``  - used by the API, analytics layer and every agent tool.
  Its role is read-only at the PostgreSQL level (see migration 008) and we
  additionally set the session to read-only so that any accidental write
  raises immediately rather than depending solely on grants.
* ``classifier_engine`` - used only by the capability classifier, the single
  component permitted to write ``work_item_capability``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()


def _build_engine(url: str, *, read_only: bool) -> Engine:
    engine = create_engine(
        url,
        pool_size=_settings.db_pool_size,
        max_overflow=_settings.db_max_overflow,
        pool_pre_ping=True,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(
                f"SET statement_timeout = {_settings.db_statement_timeout_ms}"
            )
            if read_only:
                cursor.execute("SET default_transaction_read_only = on")
        finally:
            cursor.close()

    return engine


read_engine: Engine = _build_engine(_settings.database_url, read_only=True)

classifier_engine: Engine | None = (
    _build_engine(_settings.classifier_database_url, read_only=False)
    if _settings.classifier_database_url
    else None
)

ReadSessionLocal = sessionmaker(bind=read_engine, expire_on_commit=False, future=True)
ClassifierSessionLocal = (
    sessionmaker(bind=classifier_engine, expire_on_commit=False, future=True)
    if classifier_engine
    else None
)


def get_read_session() -> Iterator[Session]:
    """FastAPI dependency yielding a read-only session."""
    session = ReadSessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def classifier_session() -> Iterator[Session]:
    """Context manager for the write-capable classifier session."""
    if ClassifierSessionLocal is None:
        raise RuntimeError(
            "CLASSIFIER_DATABASE_URL is not configured; classification is disabled."
        )
    session = ClassifierSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> bool:
    """Lightweight liveness probe used by /api/health."""
    try:
        with read_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - exercised only on real outages
        logger.exception("Database health check failed")
        return False
