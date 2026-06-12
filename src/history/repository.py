from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from history.models import QueryHistory


class HistoryRepository(Protocol):
    async def create(self, record: QueryHistory) -> QueryHistory: ...
    async def list_by_connection(self, connection_id: uuid.UUID) -> list[QueryHistory]: ...


class HistoryRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: QueryHistory) -> QueryHistory:
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_by_connection(self, connection_id: uuid.UUID) -> list[QueryHistory]:
        result = await self._session.execute(
            select(QueryHistory)
            .where(QueryHistory.connection_id == connection_id)
            .order_by(QueryHistory.created_at.desc())
        )
        return list(result.scalars().all())
