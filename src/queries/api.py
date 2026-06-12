from __future__ import annotations

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from connections.exceptions import (
    ConnectionFailedError,
    ConnectionNotFoundError,
    IntrospectionError,
)
from queries.exceptions import QueryExecutionError
from queries.schemas import ExecuteRequest, ExecuteResponse, QueryRequest, QueryResponse
from queries.service import QueryService

router = APIRouter(prefix="/connections", tags=["queries"])


@router.post("/{connection_id}/query", response_model=QueryResponse)
@inject
async def generate_sql(
    connection_id: uuid.UUID,
    request: QueryRequest,
    service: QueryService = Depends(Provide["query_service"]),
) -> QueryResponse:
    try:
        return await service.generate_sql(connection_id, request)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntrospectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{connection_id}/execute", response_model=ExecuteResponse)
@inject
async def execute_sql(
    connection_id: uuid.UUID,
    request: ExecuteRequest,
    service: QueryService = Depends(Provide["query_service"]),
) -> ExecuteResponse:
    try:
        return await service.execute_sql(connection_id, request)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConnectionFailedError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except QueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
