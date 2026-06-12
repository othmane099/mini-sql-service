from __future__ import annotations

from typing import Protocol

from sqlalchemy import NullPool, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from connections.exceptions import ConnectionFailedError
from connections.models import Connection
from queries.exceptions import QueryExecutionError
from queries.schemas import ExecuteResponse


class QueryExecutor(Protocol):
    async def execute(self, sql: str) -> ExecuteResponse: ...


class PostgreSQLQueryExecutor:
    def __init__(self, conn: Connection) -> None:
        self._dsn = (
            f"postgresql+asyncpg://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
        )

    async def execute(self, sql: str) -> ExecuteResponse:
        engine = create_async_engine(self._dsn, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(sql))
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                return ExecuteResponse(columns=columns, rows=rows)
        except OperationalError as exc:
            raise ConnectionFailedError(str(exc)) from exc
        except ConnectionFailedError, QueryExecutionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(str(exc)) from exc
        finally:
            await engine.dispose()
