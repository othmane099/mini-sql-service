from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from connections.models import Connection


class ConnectionRepository(Protocol):
    async def get_by_id(self, connection_id: uuid.UUID) -> Connection | None: ...
    async def get_by_name(self, name: str) -> Connection | None: ...
    async def list_all(self) -> list[Connection]: ...
    async def create(self, connection: Connection) -> Connection: ...
    async def delete(self, connection: Connection) -> None: ...


class ConnectionRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, connection_id: uuid.UUID) -> Connection | None:
        result = await self._session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Connection | None:
        result = await self._session.execute(select(Connection).where(Connection.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Connection]:
        result = await self._session.execute(
            select(Connection).order_by(Connection.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, connection: Connection) -> Connection:
        self._session.add(connection)
        await self._session.flush()
        await self._session.refresh(connection)
        return connection

    async def delete(self, connection: Connection) -> None:
        await self._session.delete(connection)
        await self._session.flush()
