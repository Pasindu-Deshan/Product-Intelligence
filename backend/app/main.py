"""FastAPI application entry point."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import analytics, chat, dashboard, data_quality, work_items
from app.config import get_settings
from app.database.connection import check_database

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not check_database():
        # Log loudly but still start: /api/health will report unhealthy and the
        # orchestrator can decide, rather than crash-looping the container.
        logger.error("Database is not reachable at startup.")
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Analytics and conversational intelligence over Azure DevOps time logs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    """Attach a request id so a user-facing error can be traced to a log line
    without ever exposing the underlying exception."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


# --- error handling --------------------------------------------------------
# Raw database errors and stack traces never reach the client.


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Invalid request parameters.",
            "details": [
                {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                for e in exc.errors()[:10]
            ],
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Database error (request_id=%s)", request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "A database error occurred while handling the request.",
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled error (request_id=%s)", request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected error occurred.", "request_id": request_id},
    )


# --- routes ----------------------------------------------------------------


@app.get(f"{settings.api_prefix}/health", tags=["health"])
def health() -> dict[str, object]:
    db_ok = check_database()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "llm_configured": settings.llm_enabled,
        "environment": settings.environment,
    }


for router in (
    dashboard.router,
    analytics.router,
    work_items.router,
    data_quality.router,
    chat.router,
):
    app.include_router(router, prefix=settings.api_prefix)
