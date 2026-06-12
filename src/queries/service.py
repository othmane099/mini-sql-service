from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol, cast

import structlog
from langchain_core.language_models import BaseChatModel

from connections.models import Connection
from connections.service import ConnectionService
from queries.executor import QueryExecutor
from queries.prompt import format_schema, sql_prompt
from queries.schemas import ExecuteRequest, ExecuteResponse, QueryRequest, QueryResponse

logger = structlog.get_logger()


class QueryService(Protocol):
    async def generate_sql(
        self, connection_id: uuid.UUID, request: QueryRequest
    ) -> QueryResponse: ...
    async def execute_sql(
        self, connection_id: uuid.UUID, request: ExecuteRequest
    ) -> ExecuteResponse: ...


class QueryServiceImpl:
    def __init__(
        self,
        connection_service: ConnectionService,
        llm: BaseChatModel,
        executor_factory: Callable[[Connection], QueryExecutor],
    ) -> None:
        self._connection_service = connection_service
        self._llm = llm
        self._executor_factory = executor_factory

    async def generate_sql(self, connection_id: uuid.UUID, request: QueryRequest) -> QueryResponse:
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

    async def execute_sql(
        self, connection_id: uuid.UUID, request: ExecuteRequest
    ) -> ExecuteResponse:
        conn = await self._connection_service.get_connection(connection_id)
        executor = self._executor_factory(conn)
        result = await executor.execute(request.sql)
        logger.info(
            "query.sql_executed",
            connection_id=str(connection_id),
            rows=len(result.rows),
        )
        return result
