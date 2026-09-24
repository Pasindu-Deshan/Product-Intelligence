"""Work-item endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ServiceDep
from app.schemas.work_item import WorkItemDetail

router = APIRouter(prefix="/work-items", tags=["work-items"])


@router.get("/{work_item_id}", response_model=WorkItemDetail)
def get_work_item(work_item_id: int, service: ServiceDep) -> WorkItemDetail:
    detail = service.work_item_detail(work_item_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work item {work_item_id} was not found.",
        )
    return WorkItemDetail(**detail)
