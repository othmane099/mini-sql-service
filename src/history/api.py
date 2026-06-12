from __future__ import annotations

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from history.schemas import QueryHistoryResponse
from history.service import HistoryService

router = APIRouter(prefix="/connections", tags=["history"])


@router.get("/{connection_id}/history", response_model=list[QueryHistoryResponse])
@inject
async def list_history(
    connection_id: uuid.UUID,
    service: HistoryService = Depends(Provide["history_service"]),
) -> list[QueryHistoryResponse]:
    records = await service.list_by_connection(connection_id)
    return [QueryHistoryResponse.model_validate(r) for r in records]
