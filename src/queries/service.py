from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol, cast

import structlog
from langchain_core.language_models import BaseChatModel

from connections.models import Connection
from connections.service import ConnectionService
from history.models import QueryEventType, QueryHistory
from queries.exceptions import QueryExecutionError
from queries.executor import QueryExecutor
from queries.prompt import explain_prompt, format_schema, sql_prompt
from queries.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    ExplainRequest,
    ExplainResponse,
    QueryRequest,
    QueryResponse,
)
from queries.validator import validate_select_only
from uow import UnitOfWork

logger = structlog.get_logger()


class QueryService(Protocol):
    async def generate_sql(
        self, connection_id: uuid.UUID, request: QueryRequest
    ) -> QueryResponse: ...
    async def execute_sql(
        self, connection_id: uuid.UUID, request: ExecuteRequest
    ) -> ExecuteResponse: ...
    async def explain_sql(
        self, connection_id: uuid.UUID, request: ExplainRequest
    ) -> ExplainResponse: ...


class QueryServiceImpl:
    def __init__(
        self,
        connection_service: ConnectionService,
        unit_of_work: UnitOfWork,
        llm: BaseChatModel,
        executor_factory: Callable[[Connection], QueryExecutor],
    ) -> None:
        self._connection_service = connection_service
        self._unit_of_work = unit_of_work
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
        try:
            validate_select_only(result.sql, conn.db_type)
        except QueryExecutionError as exc:
            logger.warning("query.generate.invalid_output", sql=result.sql, exc_info=exc)
            raise
        async with self._unit_of_work as uow:
            await uow.history_repository.create(
                QueryHistory(
                    connection_id=connection_id,
                    event_type=QueryEventType.GENERATE,
                    question=request.question,
                    sql=result.sql,
                    explanation=result.explanation,
                )
            )
            await uow.commit()
        logger.info(
            "query.generated",
            connection_id=str(connection_id),
            question=request.question,
        )
        return result

    async def explain_sql(
        self, connection_id: uuid.UUID, request: ExplainRequest
    ) -> ExplainResponse:
        conn = await self._connection_service.get_connection(connection_id)
        schema = await self._connection_service.get_schema(connection_id)
        chain = explain_prompt | self._llm.with_structured_output(ExplainResponse)
        result = cast(
            ExplainResponse,
            await chain.ainvoke(
                {
                    "db_type": conn.db_type.value,
                    "schema": format_schema(schema),
                    "sql": request.sql,
                }
            ),
        )
        async with self._unit_of_work as uow:
            await uow.history_repository.create(
                QueryHistory(
                    connection_id=connection_id,
                    event_type=QueryEventType.EXPLAIN,
                    sql=request.sql,
                    explanation=result.explanation,
                )
            )
            await uow.commit()
        logger.info("query.explained", connection_id=str(connection_id))
        return result

    async def execute_sql(
        self, connection_id: uuid.UUID, request: ExecuteRequest
    ) -> ExecuteResponse:
        conn = await self._connection_service.get_connection(connection_id)
        executor = self._executor_factory(conn)
        result = await executor.execute(request.sql)
        async with self._unit_of_work as uow:
            await uow.history_repository.create(
                QueryHistory(
                    connection_id=connection_id,
                    event_type=QueryEventType.EXECUTE,
                    sql=request.sql,
                    row_count=len(result.rows),
                )
            )
            await uow.commit()
        logger.info(
            "query.executed",
            connection_id=str(connection_id),
            rows=len(result.rows),
        )
        return result
