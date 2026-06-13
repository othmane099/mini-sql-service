from __future__ import annotations

from typing import Protocol
from urllib.parse import quote

import structlog
from sqlalchemy import NullPool, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings
from connections.exceptions import ConnectionFailedError
from connections.models import Connection, DBType
from queries.exceptions import QueryExecutionError
from queries.schemas import ExecuteResponse
from queries.validator import validate_select_only

logger = structlog.get_logger()


class QueryExecutor(Protocol):
    async def execute(self, sql: str) -> ExecuteResponse: ...


class PostgreSQLQueryExecutor:
    def __init__(self, conn: Connection) -> None:
        if conn.db_type != DBType.POSTGRESQL:
            raise ValueError(
                f"PostgreSQLQueryExecutor requires db_type=POSTGRESQL, got {conn.db_type}"
            )
        self._dsn = (
            f"postgresql+asyncpg://{quote(conn.username, safe='')}:{quote(conn.password, safe='')}"
            f"@{conn.host}:{conn.port}/{conn.database}"
        )

    async def execute(self, sql: str) -> ExecuteResponse:
        validate_select_only(sql, DBType.POSTGRESQL)
        engine = create_async_engine(self._dsn, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text(f"SET statement_timeout = {settings.QUERY_STATEMENT_TIMEOUT * 1000}")
                )
                result = await conn.execute(text(sql))
                columns = list(result.keys())
                raw_rows = result.fetchmany(settings.QUERY_MAX_ROWS + 1)
                truncated = len(raw_rows) > settings.QUERY_MAX_ROWS
                rows = [list(row) for row in raw_rows[: settings.QUERY_MAX_ROWS]]
                return ExecuteResponse(columns=columns, rows=rows, truncated=truncated)
        except OperationalError as exc:
            logger.warning("query.execute.connection_failed", exc_info=exc)
            raise ConnectionFailedError("could not reach the database") from exc
        except Exception as exc:
            logger.error("query.execute.error", exc_info=exc)
            raise QueryExecutionError("query execution failed") from exc
        finally:
            await engine.dispose()
