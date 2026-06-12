from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from history.models import QueryHistory


class HistoryRepository(Protocol):
    async def create(self, record: QueryHistory) -> QueryHistory: ...
    async def list_by_connection(
        self, connection_id: uuid.UUID, limit: int, offset: int
    ) -> list[QueryHistory]: ...
    async def count_by_connection(self, connection_id: uuid.UUID) -> int: ...


class HistoryRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: QueryHistory) -> QueryHistory:
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_by_connection(
        self, connection_id: uuid.UUID, limit: int, offset: int
    ) -> list[QueryHistory]:
        result = await self._session.execute(
            select(QueryHistory)
            .where(QueryHistory.connection_id == connection_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_connection(self, connection_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(QueryHistory.connection_id == connection_id)
        )
        return result.scalar_one()
