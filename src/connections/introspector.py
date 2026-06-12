from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import NullPool, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Inspector
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from connections.exceptions import ConnectionFailedError, IntrospectionError
from connections.models import Connection
from connections.schemas import ColumnInfo, TableInfo, TestConnectionResponse


class DBIntrospector(Protocol):
    async def test(self) -> TestConnectionResponse: ...
    async def introspect(self) -> list[TableInfo]: ...


class PostgreSQLIntrospector:
    _schema = "public"

    def __init__(self, conn: Connection) -> None:
        self._dsn = (
            f"postgresql+asyncpg://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}"
        )

    async def test(self) -> TestConnectionResponse:
        engine = create_async_engine(self._dsn, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return TestConnectionResponse(success=True, message="Connection successful")
        except Exception as exc:
            return TestConnectionResponse(success=False, message=str(exc))
        finally:
            await engine.dispose()

    async def introspect(self) -> list[TableInfo]:
        engine = create_async_engine(self._dsn, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(self._read_sync)
        except OperationalError as exc:
            raise ConnectionFailedError(str(exc)) from exc
        except Exception as exc:
            raise IntrospectionError(str(exc)) from exc
        finally:
            await engine.dispose()

    def _read_sync(self, sync_conn: Any) -> list[TableInfo]:
        inspector = sa_inspect(sync_conn, raiseerr=True)
        assert isinstance(inspector, Inspector)
        tables = []
        for table_name in inspector.get_table_names(schema=self._schema):
            pk_cols = set(
                inspector.get_pk_constraint(table_name, schema=self._schema).get(
                    "constrained_columns", []
                )
            )
            fk_map: dict[str, str] = {
                col: f"{fk['referred_table']}.{fk['referred_columns'][i]}"
                for fk in inspector.get_foreign_keys(table_name, schema=self._schema)
                for i, col in enumerate(fk["constrained_columns"])
            }
            tables.append(
                TableInfo(
                    name=table_name,
                    columns=[
                        ColumnInfo(
                            name=col["name"],
                            data_type=str(col["type"]),
                            nullable=col.get("nullable", True),
                            is_primary_key=col["name"] in pk_cols,
                            foreign_key=fk_map.get(col["name"]),
                        )
                        for col in inspector.get_columns(table_name, schema=self._schema)
                    ],
                )
            )
        return tables
