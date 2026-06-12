from __future__ import annotations

import uuid
from typing import Protocol, cast

import structlog
from langchain_core.language_models import BaseChatModel

from connections.service import ConnectionService
from queries.prompt import format_schema, sql_prompt
from queries.schemas import QueryRequest, QueryResponse

logger = structlog.get_logger()


class QueryService(Protocol):
    async def execute(self, connection_id: uuid.UUID, request: QueryRequest) -> QueryResponse: ...


class QueryServiceImpl:
    def __init__(
        self,
        connection_service: ConnectionService,
        llm: BaseChatModel,
    ) -> None:
        self._connection_service = connection_service
        self._llm = llm

    async def execute(self, connection_id: uuid.UUID, request: QueryRequest) -> QueryResponse:
        conn = await self._connection_service.get_connection(connection_id)
        schema = await self._connection_service.get_schema(connection_id)
        chain = sql_prompt | self._llm.with_structured_output(QueryResponse)
        result = cast(
            QueryResponse,
            await chain.ainvoke(
                {
                    "db_type": conn.db_type.value,
                    "schema": format_schema(schema),
                    "question": request.question,
                }
            ),
        )
        logger.info(
            "query.executed",
            connection_id=str(connection_id),
            question=request.question,
        )
        return result
