from __future__ import annotations

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from history.schemas import QueryHistoryResponse
from history.service import HistoryService
from schemas import PaginatedResponse

router = APIRouter(prefix="/connections", tags=["history"])


@router.get("/{connection_id}/history", response_model=PaginatedResponse[QueryHistoryResponse])
@inject
async def list_history(
    connection_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: HistoryService = Depends(Provide["history_service"]),
) -> PaginatedResponse[QueryHistoryResponse]:
    return await service.list_by_connection(connection_id, page=page, page_size=page_size)
