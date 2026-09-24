"""Data-quality endpoint.

Kept deliberately separate from analytics: quality problems are reported, never
folded into or silently corrected within the numbers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ServiceDep
from app.schemas.analytics import DataQualitySummary

router = APIRouter(tags=["data-quality"])


@router.get("/data-quality", response_model=DataQualitySummary)
def data_quality(
    service: ServiceDep,
    issue_type: Annotated[str | None, Query(max_length=100)] = None,
    severity: Annotated[str | None, Query(pattern="^(high|medium|low)$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DataQualitySummary:
    return service.data_quality(
        issue_type=issue_type, severity=severity, limit=limit, offset=offset
    )
