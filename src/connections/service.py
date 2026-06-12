from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

import structlog

from connections.exceptions import ConnectionNameConflictError, ConnectionNotFoundError
from connections.introspector import DBIntrospector
from connections.models import Connection, DBType
from connections.schemas import ConnectionCreate, SchemaResponse, TestConnectionResponse
from uow import UnitOfWork

logger = structlog.get_logger()


class ConnectionService(Protocol):
    async def list_connections(self) -> list[Connection]: ...
    async def get_connection(self, connection_id: uuid.UUID) -> Connection: ...
    async def create_connection(self, data: ConnectionCreate) -> Connection: ...
    async def delete_connection(self, connection_id: uuid.UUID) -> None: ...
    async def get_schema(self, connection_id: uuid.UUID) -> SchemaResponse: ...
    async def test_connection(self, connection_id: uuid.UUID) -> TestConnectionResponse: ...


class ConnectionServiceImpl:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        introspector_factory: Callable[[Connection], DBIntrospector],
    ) -> None:
        self._unit_of_work = unit_of_work
        self._introspector_factory = introspector_factory

    async def list_connections(self) -> list[Connection]:
        async with self._unit_of_work as uow:
            return await uow.connection_repository.list_all()

    async def get_connection(self, connection_id: uuid.UUID) -> Connection:
        async with self._unit_of_work as uow:
            conn = await uow.connection_repository.get_by_id(connection_id)
            if conn is None:
                raise ConnectionNotFoundError(connection_id)
            return conn

    async def create_connection(self, data: ConnectionCreate) -> Connection:
        async with self._unit_of_work as uow:
            if await uow.connection_repository.get_by_name(data.name) is not None:
                raise ConnectionNameConflictError(data.name)
            conn = Connection(
                db_type=DBType.POSTGRESQL,
                name=data.name,
                host=data.host,
                port=data.port,
                database=data.database,
                username=data.username,
                password=data.password,
            )
            conn = await uow.connection_repository.create(conn)
            await uow.commit()
            logger.info("connection.created", connection_id=str(conn.id), name=conn.name)
            return conn

    async def delete_connection(self, connection_id: uuid.UUID) -> None:
        async with self._unit_of_work as uow:
            conn = await uow.connection_repository.get_by_id(connection_id)
            if conn is None:
                raise ConnectionNotFoundError(connection_id)
            await uow.connection_repository.delete(conn)
            await uow.commit()
            logger.info("connection.deleted", connection_id=str(connection_id))

    async def get_schema(self, connection_id: uuid.UUID) -> SchemaResponse:
        async with self._unit_of_work as uow:
            conn = await uow.connection_repository.get_by_id(connection_id)
            if conn is None:
                raise ConnectionNotFoundError(connection_id)
        introspector = self._introspector_factory(conn)
        logger.info("connection.schema.introspecting", connection_id=str(connection_id))
        tables = await introspector.introspect()
        logger.info(
            "connection.schema.done",
            connection_id=str(connection_id),
            tables=len(tables),
        )
        return SchemaResponse(
            connection_id=conn.id,
            connection_name=conn.name,
            tables=tables,
        )

    async def test_connection(self, connection_id: uuid.UUID) -> TestConnectionResponse:
        async with self._unit_of_work as uow:
            conn = await uow.connection_repository.get_by_id(connection_id)
            if conn is None:
                raise ConnectionNotFoundError(connection_id)
        introspector = self._introspector_factory(conn)
        result = await introspector.test()
        logger.info(
            "connection.tested",
            connection_id=str(connection_id),
            success=result.success,
        )
        return result
