from __future__ import annotations

import uuid
from typing import Protocol

from history.schemas import QueryHistoryResponse
from schemas import PaginatedResponse
from uow import UnitOfWork


class HistoryService(Protocol):
    async def list_by_connection(
        self, connection_id: uuid.UUID, page: int, page_size: int
    ) -> PaginatedResponse[QueryHistoryResponse]: ...


class HistoryServiceImpl:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def list_by_connection(
        self, connection_id: uuid.UUID, page: int, page_size: int
    ) -> PaginatedResponse[QueryHistoryResponse]:
        offset = (page - 1) * page_size
        async with self._unit_of_work as uow:
            total = await uow.history_repository.count_by_connection(connection_id)
            records = await uow.history_repository.list_by_connection(
                connection_id, limit=page_size, offset=offset
            )
        items = [QueryHistoryResponse.model_validate(r) for r in records]
        return PaginatedResponse.build(items=items, total=total, page=page, page_size=page_size)
