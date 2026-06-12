from __future__ import annotations

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from connections.exceptions import (
    ConnectionFailedError,
    ConnectionNameConflictError,
    ConnectionNotFoundError,
    IntrospectionError,
)
from connections.schemas import (
    ConnectionCreate,
    ConnectionResponse,
    SchemaResponse,
    TestConnectionResponse,
)
from connections.service import ConnectionService

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionResponse])
@inject
async def list_connections(
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> list[ConnectionResponse]:
    connections = await service.list_connections()
    return [ConnectionResponse.model_validate(c) for c in connections]


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_connection(
    data: ConnectionCreate,
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> ConnectionResponse:
    try:
        conn = await service.create_connection(data)
        return ConnectionResponse.model_validate(conn)
    except ConnectionNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{connection_id}", response_model=ConnectionResponse)
@inject
async def get_connection(
    connection_id: uuid.UUID,
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> ConnectionResponse:
    try:
        conn = await service.get_connection(connection_id)
        return ConnectionResponse.model_validate(conn)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_connection(
    connection_id: uuid.UUID,
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> None:
    try:
        await service.delete_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{connection_id}/schema", response_model=SchemaResponse)
@inject
async def get_schema(
    connection_id: uuid.UUID,
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> SchemaResponse:
    try:
        return await service.get_schema(connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConnectionFailedError, IntrospectionError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{connection_id}/test", response_model=TestConnectionResponse)
@inject
async def test_connection(
    connection_id: uuid.UUID,
    service: ConnectionService = Depends(Provide["connection_service"]),
) -> TestConnectionResponse:
    try:
        return await service.test_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
