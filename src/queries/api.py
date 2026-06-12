from __future__ import annotations

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from connections.exceptions import ConnectionNotFoundError, IntrospectionError
from queries.schemas import QueryRequest, QueryResponse
from queries.service import QueryService

router = APIRouter(prefix="/connections", tags=["queries"])


@router.post("/{connection_id}/query", response_model=QueryResponse)
@inject
async def execute_query(
    connection_id: uuid.UUID,
    request: QueryRequest,
    service: QueryService = Depends(Provide["query_service"]),
) -> QueryResponse:
    try:
        return await service.execute(connection_id, request)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntrospectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
