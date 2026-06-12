from __future__ import annotations

import uuid
from typing import Protocol

from history.models import QueryHistory
from uow import UnitOfWork


class HistoryService(Protocol):
    async def list_by_connection(self, connection_id: uuid.UUID) -> list[QueryHistory]: ...


class HistoryServiceImpl:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def list_by_connection(self, connection_id: uuid.UUID) -> list[QueryHistory]:
        async with self._unit_of_work as uow:
            return await uow.history_repository.list_by_connection(connection_id)
